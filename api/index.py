import os
import json
import asyncio
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from flask_cors import CORS # Re-import the CORS library
from dotenv import load_dotenv
import libsql_client
import re

app = Flask(__name__)

# --- THIS IS THE FINAL FIX ---
# This correctly initializes the CORS extension to handle all requests,
# including the preflight OPTIONS requests that were causing the error.
CORS(app)
# --- END OF FINAL FIX ---

TABLE_NAME = "articles"
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80"

def create_db_client():
    url = os.getenv("TURSO_DATABASE_URL")
    auth_token = os.getenv("TURSO_AUTH_TOKEN")
    if not url or not auth_token:
        print("DATABASE ERROR: Missing Turso credentials.")
        return None
    url = url.replace("libsql://", "https://")
    return libsql_client.create_client(url=url, auth_token=auth_token)

# This is the original date formatting function
def format_date_for_display(date_obj):
    if not date_obj: return "Unknown Date"
    try:
        now = datetime.now(timezone.utc)
        if date_obj.tzinfo is None: date_obj = date_obj.replace(tzinfo=timezone.utc)
        delta = now - date_obj
        if delta.days == 0: return f"Today, {date_obj.strftime('%b %d')}"
        elif delta.days == 1: return f"Yesterday, {date_obj.strftime('%b %d')}"
        elif delta.days < 7: return f"{delta.days} days ago"
        else: return date_obj.strftime('%b %d, %Y')
    except Exception: return "Invalid Date"

def rows_to_dict_list(rows):
    if not rows: return []
    return [dict(zip(rows.columns, row)) for row in rows]

async def query_articles_async(filters):
    client = create_db_client()
    if not client: return []
    try:
        base_query, params = f"SELECT * FROM {TABLE_NAME}", []
        where_clauses = []
        if filters.get('category') and filters['category'] != "All Categories":
            where_clauses.append("article_category = ?"); params.append(filters['category'])
        if filters.get('search'):
            search_term = f"%{filters['search'].lower()}%"
            where_clauses.append("(LOWER(original_title) LIKE ? OR LOWER(llm_generated_title) LIKE ? OR LOWER(article_description) LIKE ? OR LOWER(source) LIKE ? OR LOWER(article_content) LIKE ?)")
            params.extend([search_term] * 5)
        if filters.get('month') and filters['month'] != "All Months":
            month_param = filters['month']
            # if it's in ISO format "YYYY-MM", use %Y-%m, otherwise fall back to human "%Y - %B"
            if re.match(r'^\d{4}-\d{2}$', month_param):
                where_clauses.append("strftime('%Y-%m', published_at_iso) = ?")
                params.append(month_param)
            else:
                where_clauses.append("strftime('%Y - %B', published_at_iso) = ?")
                params.append(month_param)

        if where_clauses: base_query += " WHERE " + " AND ".join(where_clauses)
        
        sort_map = {"Newest First": "published_at_iso DESC", "Oldest First": "published_at_iso ASC", "A-Z": "original_title ASC", "Z-A": "original_title DESC"}
        sort_order = sort_map.get(filters.get('sort_option'), "published_at_iso DESC")
        base_query += f" ORDER BY {sort_order} LIMIT 50"
        
        result_set = await client.execute(base_query, params)
        articles = rows_to_dict_list(result_set)
        for article_dict in articles:
            def safe_json_loads(x):
                if not isinstance(x, str) or not x: return []
                try: return json.loads(x)
                except Exception: return []
            article_dict["historical_context"] = safe_json_loads(article_dict.get("historical_context"))
            article_dict["glossary"] = safe_json_loads(article_dict.get("glossary"))
            if not article_dict.get(IMAGE_COLUMN_NAME): article_dict[IMAGE_COLUMN_NAME] = DEFAULT_IMAGE
            try:
                iso_str = article_dict.get('published_at_iso', '')
                if iso_str:
                    if iso_str.endswith('Z'): iso_str = iso_str[:-1] + '+00:00'
                    dt_obj = datetime.fromisoformat(iso_str)
                    article_dict['published_at_formatted'] = format_date_for_display(dt_obj)
                else: article_dict['published_at_formatted'] = "Unknown Date"
            except Exception: article_dict['published_at_formatted'] = "Unknown Date"
        return articles
    finally:
        if client: await client.close()

async def get_filter_options_async():
    client = create_db_client()
    if not client: return {"error": "DB connection failed"}
    options = {"categories": ["All Categories"], "months": ["All Months"], "days_by_month": {"All Months": ["All Days"]}, "all_unique_days": ["All Days"]}
    try:
        cat_rows = await client.execute(f"SELECT DISTINCT article_category FROM {TABLE_NAME} WHERE article_category IS NOT NULL AND article_category != ''")
        options["categories"].extend(sorted(list(set([row[0] for row in cat_rows if row[0]]))))
        
        date_rows = await client.execute(f"SELECT DISTINCT published_at_iso FROM {TABLE_NAME} WHERE published_at_iso IS NOT NULL AND published_at_iso != ''")
        dates_str = [row[0] for row in date_rows]
        if dates_str:
            all_dates = []
            for date_s in dates_str:
                try:
                    if date_s.endswith('Z'): date_s = date_s[:-1] + '+00:00'
                    all_dates.append(datetime.fromisoformat(date_s))
                except Exception: continue
            if all_dates:
                options["months"].extend(sorted(list(set([d.strftime('%Y - %B') for d in all_dates])), key=lambda d: datetime.strptime(d, '%Y - %B'), reverse=True))
                days_by_month_dict = {}
                for d in all_dates:
                    ym_str = d.strftime('%Y - %B');
                    if ym_str not in days_by_month_dict: days_by_month_dict[ym_str] = set()
                    days_by_month_dict[ym_str].add(str(d.day))
                for ym_str, days_set in days_by_month_dict.items():
                    options["days_by_month"][ym_str] = ["All Days"] + sorted(list(days_set), key=int)
                options["all_unique_days"].extend(sorted(list(set([str(d.day) for d in all_dates])), key=int))
        return options
    finally:
        if client: await client.close()

@app.route('/articles', methods=['GET'])
def get_articles():
    filters = {'search': request.args.get('search'), 'sort_option': request.args.get('sort'), 'month': request.args.get('month'), 'day': request.args.get('day'), 'category': request.args.get('category')}
    articles_data = asyncio.run(query_articles_async(filters))
    return jsonify(articles_data)

@app.route('/filter-options', methods=['GET'])
def get_filter_options():
    options = asyncio.run(get_filter_options_async())
    if "error" in options: return jsonify(options), 500
    return jsonify(options)
