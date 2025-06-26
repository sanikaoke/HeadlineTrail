import os
import json
import sqlite3
import shutil
from datetime import datetime, timezone
from dotenv import load_dotenv

print("--- Starting static site build ---")

# --- Load Environment Variables ---
# On Vercel, these will be set in the project settings.
load_dotenv()
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
TABLE_NAME = "articles"
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80"

# --- Database Connection ---
def get_db_connection():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise Exception("Error: Missing Turso credentials.")
    url = TURSO_DATABASE_URL.replace("libsql://", "https://")
    return sqlite3.connect(f"{url}?authToken={TURSO_AUTH_TOKEN}&secure=true", uri=True)

# --- Date Formatting ---
def format_date_for_display(date_obj):
    if not date_obj: return "Unknown Date"
    try:
        now = datetime.now(timezone.utc)
        if date_obj.tzinfo is None: date_obj = date_obj.replace(tzinfo=timezone.utc)
        delta = now - date_obj
        if delta.days == 0: return f"Today, {date_obj.strftime('%b %d')}"
        elif delta.days == 1: return f"Yesterday, {date_obj.strftime('%b %d')}"
        else: return date_obj.strftime('%b %d, %Y')
    except Exception: return "Invalid Date"

# --- Main Build Logic ---
def build_site():
    print("Connecting to database...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Fetching all articles...")
    cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY published_at_iso DESC")
    rows = cursor.fetchall()
    conn.close()
    print(f"Found {len(rows)} articles.")

    articles = []
    for row in rows:
        article_dict = dict(row)
        try:
            iso_str = article_dict.get('published_at_iso', '')
            if iso_str:
                if iso_str.endswith('Z'): iso_str = iso_str[:-1] + '+00:00'
                article_dict['published_at_formatted'] = format_date_for_display(datetime.fromisoformat(iso_str))
            else: article_dict['published_at_formatted'] = "Unknown Date"
        except Exception
