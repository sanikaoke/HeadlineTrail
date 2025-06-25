# backend_api.py (Handles data retrieval and filtering)
import sqlite3
import pandas as pd
import json
from flask import Flask, jsonify, request # Added request
from flask_cors import CORS # Import CORS
import os
from datetime import datetime
from dotenv import load_dotenv # Ensure dotenv is imported if used for keys
from update_db import process_and_store_articles  # Add this import at the top

print("--- Backend API Starting ---")

# --- Load Keys (Optional: Only needed if backend performs actions requiring keys) ---
# print("Loading API keys from .env file...")
# load_dotenv()
# NEWS_API_KEY = os.getenv("NEWS_API_KEY")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Database Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "news_data.db" # Make sure this file exists and is populated
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
TABLE_NAME = "articles"
print(f"Using database at: {DB_PATH}")

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for requests from your frontend domain
print("Flask app created and CORS enabled.")

# --- Constants ---
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80" # Generic News Image

# --- Database Helper ---
def get_db_connection():
    """Creates a connection to the Turso cloud SQLite database."""
    # These will be read from Vercel's environment variables
    url = os.getenv("TURSO_DATABASE_URL")
    auth_token = os.getenv("TURSO_AUTH_TOKEN")

    if not url or not auth_token:
        print("DATABASE ERROR: Missing TURSO_DATABASE_URL or TURSO_AUTH_TOKEN environment variables.")
        return None
    try:
        # Connect to Turso using the libsql-client format
        conn = sqlite3.connect(f"file:{url}?authToken={auth_token}&secure=true", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# --- Date Formatting Helper ---
def format_date_for_display(date_obj):
    """Formats datetime object for display."""
    if not date_obj or pd.isna(date_obj): return "Unknown Date"
    try:
        # Convert to timezone-naive if necessary
        if date_obj.tzinfo is not None: date_obj = date_obj.tz_convert(None)
        now = datetime.now()
        delta = now - date_obj
        if delta.days == 0: return f"Today, {date_obj.strftime('%b %d')}"
        elif delta.days == 1: return f"Yesterday, {date_obj.strftime('%b %d')}"
        elif delta.days < 7: return f"{delta.days} days ago"
        else: return date_obj.strftime('%b %d, %Y')
    except Exception as e:
        print(f"Warn: Date formatting error {e}")
        return "Invalid Date"

# --- Function to Query and Filter Data ---
def query_articles(filters):
    # --- Function to Query and Filter Data ---
def query_articles(filters):
    """Queries the DB using SQL and applies filters directly in the query."""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        # Base query
        base_query = f"SELECT * FROM {TABLE_NAME}"
        where_clauses = []
        params = []

        # Category Filter
        selected_category = filters.get('category')
        if selected_category and selected_category != "All Categories":
            where_clauses.append("article_category = ?")
            params.append(selected_category)

        # Search Query Filter
        search_query = filters.get('search')
        if search_query:
            search_term = f"%{search_query.lower()}%"
            search_clause = """
                (LOWER(original_title) LIKE ? OR 
                 LOWER(llm_generated_title) LIKE ? OR 
                 LOWER(article_description) LIKE ? OR 
                 LOWER(source) LIKE ? OR 
                 LOWER(article_content) LIKE ?)
            """
            where_clauses.append(search_clause)
            params.extend([search_term] * 5)

        # Date Filter Logic
        selected_month_str = filters.get('month')
        selected_day_str = filters.get('day')

        if selected_month_str and selected_month_str != "All Months":
            where_clauses.append("strftime('%Y - %B', published_at_iso) = ?")
            params.append(selected_month_str)
        
        if selected_day_str and selected_day_str != "All Days":
            # This filters by the day number regardless of month if "All Months" is selected,
            # or within a specific month if a month is selected.
            where_clauses.append("strftime('%d', published_at_iso) = ?")
            # Pad with leading zero if needed, e.g., '5' -> '05'
            params.append(selected_day_str.zfill(2))

        # Combine all WHERE clauses
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
            
        # Sort Order
        sort_option = filters.get('sort_option', 'Newest First')
        if sort_option == "Newest First":
            base_query += " ORDER BY published_at_iso DESC"
        elif sort_option == "Oldest First":
            base_query += " ORDER BY published_at_iso ASC"
        elif sort_option == "A-Z":
            base_query += " ORDER BY original_title ASC"
        elif sort_option == "Z-A":
            base_query += " ORDER BY original_title DESC"

        # Execute the query
        cursor = conn.cursor()
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        conn.close()

        # --- Prepare data for JSON response ---
        articles = []
        for row in rows:
            article_dict = dict(row) # Convert sqlite3.Row to a dictionary

            def safe_json_loads(x):
                if not isinstance(x, str) or x.strip() == "" or x == "N/A":
                    return []
                try:
                    return json.loads(x)
                except (json.JSONDecodeError, TypeError):
                    return []

            article_dict["historical_context"] = safe_json_loads(article_dict.get("historical_context"))
            article_dict["glossary"] = safe_json_loads(article_dict.get("glossary"))

            img_url = article_dict.get(IMAGE_COLUMN_NAME)
            if not img_url or not isinstance(img_url, str) or not img_url.startswith('http'):
                article_dict[IMAGE_COLUMN_NAME] = DEFAULT_IMAGE

            # Format date for display
            try:
                dt_obj = datetime.fromisoformat(article_dict['published_at_iso'].replace('Z', '+00:00'))
                article_dict['published_at_formatted'] = format_date_for_display(dt_obj)
            except (ValueError, TypeError):
                article_dict['published_at_formatted'] = "Unknown Date"
            
            articles.append(article_dict)

        print(f"Returning {len(articles)} filtered/sorted articles.")
        return articles

    except Exception as e:
        print(f"Error querying/processing DB: {e}")
        if conn:
            conn.close()
        return []
# --- API Endpoint for Articles ---
@app.route('/articles', methods=['GET'])
def get_articles():
    """Endpoint to fetch articles, accepts filter params."""
    print("\nReceived request for /articles")
    # Get filter parameters from request URL query string
    search_query = request.args.get('search', default=None, type=str)
    sort_option = request.args.get('sort', default="Newest First", type=str)
    selected_month = request.args.get('month', default="All Months", type=str)
    selected_day = request.args.get('day', default="All Days", type=str)
    # Changed category to single value for standard select
    selected_category = request.args.get('category', default="All Categories", type=str)

    print(f"Filters received: Search='{search_query}', Sort='{sort_option}', Category='{selected_category}', Month='{selected_month}', Day='{selected_day}'")
    filters = {
        'search': search_query,
        'category': selected_category, # Pass single category
        'sort_option': sort_option,
        'month': selected_month,
        'day': selected_day,
    }
    articles_data = query_articles(filters)
    response = jsonify(articles_data)
    print(f"Sending response with {len(articles_data)} articles.")
    return response

# --- API Endpoint for Filter Options ---
@app.route('/filter-options', methods=['GET'])
def get_filter_options():
    """Endpoint to get available categories, date ranges, and all unique days."""
    print("\nReceived request for /filter-options")
    if not os.path.exists(DB_PATH): return jsonify({"error": f"DB not found."}), 500
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB connection failed"}), 500

    # Initialize options structure
    options = {
        "categories": ["All Categories"],
        "months": ["All Months"],
        "days_by_month": {"All Months": ["All Days"]}, # Days specific to each month
        "all_unique_days": ["All Days"] # All unique days across the dataset
    }
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}';")
        if cursor.fetchone() is None: 
            conn.close()
            return jsonify({"error": f"Table not found."}), 500

        # Get categories
        cursor.execute(f"SELECT DISTINCT article_category FROM {TABLE_NAME} WHERE article_category IS NOT NULL AND article_category != 'N/A'")
        cats = [row[0] for row in cursor.fetchall()]
        if "Other" in cats: 
            cats.remove("Other")
        else: 
            cats.append("Other")
        options["categories"].extend(sorted(cats))

        # Get dates
        date_col_to_query = "published_at_iso" # Use indexed column
        cursor.execute(f"SELECT DISTINCT {date_col_to_query} FROM {TABLE_NAME} WHERE {date_col_to_query} IS NOT NULL AND {date_col_to_query} != ''")
        dates_str = [row[0] for row in cursor.fetchall()]
        conn.close() # Close connection
        #print("DATE",dates_str)
        if dates_str:
            dates_dt = pd.to_datetime(dates_str, errors='coerce', utc=True).dropna().tz_convert(None)
            #print(dates_dt)
            if not dates_dt.empty:
                # Get Months and Days per Month
                year_month_strs = dates_dt.strftime('%Y - %B').unique()
                sorted_months = pd.to_datetime(year_month_strs, format='%Y - %B').sort_values(ascending=False).strftime('%Y - %B').tolist()
                options["months"].extend(sorted_months)
                for ym_str in sorted_months:
                    try: 
                        year_str, month_name = ym_str.split(' - ', 1) 
                        year = int(year_str)
                        month_num = datetime.strptime(month_name, "%B").month
                        days = sorted(dates_dt[(dates_dt.year == year) & (dates_dt.month == month_num)].day.unique().tolist())
                        options["days_by_month"][ym_str] = ["All Days"] + [str(d) for d in days]
                    except Exception as e: print(f"Error parsing days for {ym_str}: {e}")

                # Get All Unique Days across dataset
                all_days = sorted(dates_dt.day.unique().tolist())
                options["all_unique_days"].extend([str(d) for d in all_days])
                #print(options)
        print("Filter options prepared successfully")
        return jsonify(options)
    except Exception as e:
        print(f"Error fetching filter options: {e}")
        if conn:
            conn.close()
        return jsonify({"error": "Failed to retrieve filter options"}), 500

@app.route('/api/fetch-latest-news', methods=['POST'])
def fetch_latest_news():
    """Endpoint to fetch and process latest news articles."""
    try:
        print("\n--- Starting Fetch Latest News Request ---")
        response_data = {
            'success': False,
            'message': '',
            'new_articles_count': 0,
            'details': {
                'dates_processed': [],
                'articles_per_date': {},
                'errors': []
            }
        }

        # Load and verify API keys
        load_dotenv()
        NEWS_API_KEY = os.getenv("NEWS_API_KEY")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

        if not NEWS_API_KEY or not OPENAI_API_KEY:
            error_msg = 'Missing API keys: ' + \
                       ('NEWS_API_KEY ' if not NEWS_API_KEY else '') + \
                       ('OPENAI_API_KEY' if not OPENAI_API_KEY else '')
            print(f"Error: {error_msg}")
            response_data['message'] = error_msg
            return jsonify(response_data), 500

        try:
            # Call process_and_store_articles with detailed logging
            print("Calling process_and_store_articles...")
            result = process_and_store_articles()
            print(f"Result from process_and_store_articles: {result}")
            
            # Handle boolean result for backward compatibility
            if isinstance(result, bool):
                if result:
                    response_data['success'] = True
                    response_data['message'] = "Successfully processed new articles"
                else:
                    response_data['message'] = "Failed to process articles"
                    return jsonify(response_data), 500
            elif isinstance(result, dict):
                response_data.update(result)
            else:
                error_msg = f'Invalid result format from process_and_store_articles: {result}'
                print(f"Error: {error_msg}")
                response_data['message'] = error_msg
                return jsonify(response_data), 500

            return jsonify(response_data), 200

        except Exception as e:
            error_msg = f'Error during processing: {str(e)}'
            print(f"Error: {error_msg}")
            response_data['details']['errors'].append(str(e))
            response_data['message'] = error_msg
            return jsonify(response_data), 500

    except Exception as e:
        error_msg = f'Unexpected error: {str(e)}'
        print(f"Error: {error_msg}")
        return jsonify({
            'success': False,
            'message': error_msg,
            'details': {'errors': [str(e)]}
        }), 500
    
# --- Run the Flask App ---
if __name__ == '__main__':
    print("Starting Flask development server on http://127.0.0.1:5001")
    # Set host='0.0.0.0' to make it accessible on your network (optional)
    app.run(debug=True, port=5001)
