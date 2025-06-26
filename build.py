import os
import json
import asyncio
import shutil
from datetime import datetime, timezone
from dotenv import load_dotenv
import libsql_client

print("--- Starting static site build ---")

# --- Load Environment Variables ---
load_dotenv()
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
TABLE_NAME = "articles"
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80"

# --- Database Helper (using libsql_client directly) ---
def create_db_client():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise Exception("Error: Missing Turso credentials.")
    url = TURSO_DATABASE_URL.replace("libsql://", "https://")
    return libsql_client.create_client(url=url, auth_token=TURSO_AUTH_TOKEN)

# --- Date Formatting Helper ---
def format_date_for_display(date_obj):
    if not date_obj: return "Unknown Date"
    try:
        now = datetime.now(timezone.utc)
        if date_obj.tzinfo is None: date_obj = date_obj.replace(tzinfo=timezone.utc)
        delta = now - date_obj
        if delta.days == 0: return f"Today, {date_obj.strftime('%b %d')}"
        elif delta.days == 1: return f"Yesterday, {date_obj.strftime('%b %d')}"
        else: return f"{delta.days} days ago"
    except Exception: return "Invalid Date"

def rows_to_dict_list(rows):
    if not rows: return []
    return [dict(zip(rows.columns, row)) for row in rows]

# --- Main Async Build Logic ---
async def build_site_async():
    print("Connecting to database using libsql-client...")
    client = create_db_client()
    
    try:
        print("Fetching all articles...")
        result_set = await client.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY published_at_iso DESC")
        articles_raw = rows_to_dict_list(result_set)
        print(f"Found {len(articles_raw)} articles.")

        articles = []
        for article_dict in articles_raw:
            try:
                iso_str = article_dict.get('published_at_iso', '')
                if iso_str:
                    if iso_str.endswith('Z'): iso_str = iso_str[:-1] + '+00:00'
                    article_dict['published_at_formatted'] = format_date_for_display(datetime.fromisoformat(iso_str))
                else: article_dict['published_at_formatted'] = "Unknown Date"
            except Exception: article_dict['published_at_formatted'] = "Unknown Date"
            articles.append(article_dict)

        # --- Generate HTML for News Cards ---
        cards_html = ""
        if not articles:
            cards_html = "<div id='no-results-message' style='grid-column: 1 / -1; text-align: center;'>No articles found.</div>"
        else:
            for article in articles:
                image_url = article.get(IMAGE_COLUMN_NAME) or DEFAULT_IMAGE
                title = article.get('original_title', 'Untitled').replace('<', '&lt;').replace('>', '&gt;')
                source = article.get('source', 'Unknown').replace('<', '&lt;').replace('>', '&gt;')
                date_str = article.get('published_at_formatted', 'Unknown Date')
                article_id = article.get('original_url')

                cards_html += f"""
                <div class="news-card">
                    <img src="{image_url}" alt="" onerror="this.onerror=null;this.src='{DEFAULT_IMAGE}';">
                    <div class="card-content">
                        <h6>{title}</h6>
                        <div class="caption">{source} | {date_str}</div>
                        <button data-article-id="{article_id}">Read Article</button>
                    </div>
                </div>
                """
        
        # --- Read HTML template and inject content ---
        print("Reading HTML template...")
        with open('index.html', 'r', encoding='utf-8') as f:
            template = f.read()

        final_html = template.replace("{/* News cards inserted here */}", cards_html)
        
        all_articles_json = json.dumps(articles)
        final_html = final_html.replace(
            "", 
            f'<script id="articles-data" type="application/json">{all_articles_json}</script>'
        )

        # --- Create 'public' directory and save the final files ---
        if not os.path.exists('public'):
            os.makedirs('public')
        
        with open('public/index.html', 'w', encoding='utf-8') as f:
            f.write(final_html)

        shutil.copy('style.css', 'public/style.css')
        shutil.copy('script.js', 'public/script.js')

        print("--- Build complete! Site generated in 'public' folder. ---")

    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    # This runs the main async function
    asyncio.run(build_site_async())
