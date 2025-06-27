import os
import json
import asyncio
import shutil
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
import libsql_client

print("--- Starting multi-page static site build ---")

# --- Configuration ---
load_dotenv()
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
TABLE_NAME = "articles"
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80"
ARTICLES_TO_BUILD = 20

# --- Database Helper ---
def create_db_client():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise Exception("Error: Missing Turso credentials.")
    # This is the corrected line
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

def create_slug(text):
    """Creates a URL-friendly slug from a title."""
    text = str(text).lower()
    text = re.sub(r'[\s\W]+', '-', text) # Replace spaces and non-word characters with a dash
    return text.strip('-')[:80] # Limit length

# --- Main Async Build Logic ---
async def build_site_async():
    print("Connecting to database...")
    client = create_db_client()
    try:
        print(f"Fetching Top {ARTICLES_TO_BUILD} articles...")
        query = f"SELECT * FROM {TABLE_NAME} ORDER BY published_at_iso DESC LIMIT {ARTICLES_TO_BUILD}"
        result_set = await client.execute(query)
        articles = rows_to_dict_list(result_set)
        print(f"Found {len(articles)} articles.")

        # --- Create output directories ---
        if os.path.exists('public'): shutil.rmtree('public')
        os.makedirs('public/articles')

        # --- Read Templates ---
        with open('index.html', 'r', encoding='utf-8') as f: index_template = f.read()
        with open('detail.html', 'r', encoding='utf-8') as f: detail_template = f.read()
        
        # --- Generate Index Page ---
        cards_html = ""
        for article in articles:
            # Prepare data for the card
            image_url = article.get(IMAGE_COLUMN_NAME) or DEFAULT_IMAGE
            title = str(article.get('original_title', 'Untitled')).replace('<', '&lt;').replace('>', '&gt;')
            source = str(article.get('source', 'Unknown')).replace('<', '&lt;').replace('>', '&gt;')
            
            iso_str = article.get('published_at_iso', '')
            date_str = "Unknown Date"
            if iso_str:
                try:
                    if iso_str.endswith('Z'): iso_str = iso_str[:-1] + '+00:00'
                    date_str = format_date_for_display(datetime.fromisoformat(iso_str))
                except Exception: pass
            
            slug = create_slug(title)
            detail_page_url = f"/articles/{slug}.html"

            cards_html += f"""
            <div class="news-card">
                <a href="{detail_page_url}" class="card-link-wrapper">
                    <img src="{image_url}" alt="" onerror="this.onerror=null;this.src='{DEFAULT_IMAGE}';">
                    <div class="card-content">
                        <h6>{title}</h6>
                        <div class="caption">{source} | {date_str}</div>
                    </div>
                </a>
            </div>
            """
        
        final_index_html = index_template.replace("", cards_html)
        with open('public/index.html', 'w', encoding='utf-8') as f:
            f.write(final_index_html)
        print("Generated index.html")

        # --- Generate Individual Article Pages ---
        for article in articles:
            # This logic needs the original date string formatting
            iso_str = article.get('published_at_iso', '')
            date_str = "Unknown Date"
            if iso_str:
                try:
                    if iso_str.endswith('Z'): iso_str = iso_str[:-1] + '+00:00'
                    date_str = format_date_for_display(datetime.fromisoformat(iso_str))
                except Exception: pass

            # Generate timeline HTML
            timeline_html = "<p>No timeline entries available.</p>"
            timeline_data = json.loads(article.get('historical_context') or '[]')
            if timeline_data:
                timeline_html = ""
                for entry in timeline_data:
                    timeline_html += f"<div><p><strong>{entry.get('year', '?')}: {entry.get('title', 'Event')}</strong></p><p style='margin-top: 0.2em;'>{entry.get('summary', '')}</p></div>"

            # Generate glossary HTML
            glossary_html = "<p>No glossary terms available.</p>"
            glossary_data = json.loads(article.get('glossary') or '[]')
            if glossary_data:
                glossary_html = ""
                for entry in glossary_data:
                    glossary_html += f"<div><strong>{entry.get('word', '?')}:</strong> {entry.get('definition', '')}</div>"

            # Generate Read More button HTML
            read_more_html = ""
            if article.get('original_url'):
                read_more_html = f'<a href="{article.get("original_url")}" class="read-more-button" target="_blank" rel="noopener noreferrer">📰 Read Full Article Online</a>'

            # Replace placeholders in the detail template
            article_page_html = detail_template.replace("", str(article.get('original_title', 'Untitled')))
            article_page_html = article_page_html.replace("", f"Source: {article.get('source', 'Unknown')} | Published: {date_str}")
            article_page_html = article_page_html.replace("", f'<img id="detail-image" src="{article.get(IMAGE_COLUMN_NAME) or DEFAULT_IMAGE}" alt="Article Image" onerror="this.onerror=null;this.src=\'{DEFAULT_IMAGE}\';">')
            article_page_html = article_page_html.replace("", str(article.get('article_content', 'Content not available.')))
            article_page_html = article_page_html.replace("", timeline_html)
            article_page_html = article_page_html.replace("", glossary_html)
            article_page_html = article_page_html.replace("", read_more_html)

            # Save the new file
            slug = create_slug(article.get('original_title', 'Untitled'))
            with open(f"public/articles/{slug}.html", "w", encoding="utf-8") as f:
                f.write(article_page_html)

        print(f"Generated {len(articles)} individual article pages.")
        
        # --- Copy static assets ---
        shutil.copy('style.css', 'public/style.css')
        shutil.copy('script.js', 'public/script.js')

        print("--- Build complete! Site generated in 'public' folder. ---")

    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(build_site_async())
