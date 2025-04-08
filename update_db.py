# ==============================================================================
# update_db.py - Backend Script
# Fetches, Scrapes, Processes News and Stores in SQLite DB
# ==============================================================================
print("--- Backend Script Started: Importing Libraries ---")
import pandas as pd
import os
import time
import requests
import json
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Dict # Added Dict
from newspaper import Article, ArticleException # Import newspaper3k
from dotenv import load_dotenv
import sqlite3 # Import SQLite library
from datetime import datetime

print("Libraries imported.")

# ==============================================================================
# API KEY CONFIGURATION & CLIENT INITIALIZATION
# ==============================================================================
print("Loading API keys from .env file...")
load_dotenv() # Load environment variables from .env file

# Get keys from environment
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Ensure this is set in your .env

# --- Configure OpenAI Client ---
openai_client = None
keys_valid = True
if NEWS_API_KEY and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client configured successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR configuring OpenAI client: {e}")
        keys_valid = False
        openai_client = None
else:
    missing_keys = []
    if not NEWS_API_KEY: missing_keys.append("NewsAPI Key")
    if not OPENAI_API_KEY: missing_keys.append("OpenAI Key")
    print(f"CRITICAL API Key Error: Missing {', '.join(missing_keys)} in .env file.")
    keys_valid = False
    openai_client = None

if not keys_valid:
    print("Exiting script due to missing or invalid API Keys.")
    exit() # Stop the script if keys are bad

# ==============================================================================
# DEFINITIONS (Pydantic Models, Prompt, Helpers, DB Functions)
# ==============================================================================

# --- Pydantic Models ---
class TimelineEntry(BaseModel):
    year: str
    title: str
    summary: str
class GlossaryEntry(BaseModel):
    word: str
    definition: str
class OutputResponseFormat(BaseModel):
    title_entry: str
    timeline_entries: List[TimelineEntry]
    glossary_entries: List[GlossaryEntry]
    article_category: str
print("Pydantic models defined.")

# --- Meta Prompt ---
ALLOWED_CATEGORIES = ["Politics", "Business", "Technology", "Health", "Science", "Sports", "Entertainment", "World News", "US News", "Other"]
# Make sure the placeholder {} is present for article text insertion
meta_prompt = f"""Given a news article, perform the following tasks:

Here's the news article:
{{}}

Output

  1. **Title:** Based on the news article, come up with a relevant title for the article.
  2. **Historical Context Timeline:** Create a chronological timeline of the key historical events that directly contribute to understanding the current news article. Format each entry as:
  **[YEAR/PERIOD] - [BRIEF DESCRIPTIVE HEADLINE]**
  [A single paragraph of 4-6 sentences explaining: what happened, who the key players were (with necessary background about these people/groups), the situation at that time, and why these events occurred. Use language an average high school student can understand.]
  *[1-2 sentences explicitly connecting this historical event to the current news article.]*
    (Timeline Content Requirements: Focus only on relevant events, provide context, explain importance, use accessible language)

  3. **Glossary of Terms:** Include a section that defines any complex terms, jargon, or unfamiliar concepts mentioned in the article or timeline using extremely simple language.

  4. **Category Assignment:** Assign the **single most relevant category** to this article from the following list: {', '.join(ALLOWED_CATEGORIES)}. Output only the chosen category name.
"""
print("Meta prompt defined.")

# --- Database Setup ---
DB_NAME = "news_data.db"
TABLE_NAME = "articles"

def init_db():
    """Initializes the SQLite database and creates the table if it doesn't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Added NOT NULL constraint to primary key for robustness
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                original_url TEXT PRIMARY KEY NOT NULL,
                original_title TEXT,
                llm_generated_title TEXT,
                source TEXT,
                published_at TEXT,
                published_at_iso TEXT, -- Store ISO format for easier sorting
                article_description TEXT,
                article_content TEXT, -- Store scraped/fallback text
                article_url_to_image TEXT,
                historical_context TEXT, -- Store as JSON string
                glossary TEXT,           -- Store as JSON string
                article_category TEXT,
                llm_input_source TEXT,
                last_updated TEXT -- Track when record was added/updated
            )
        ''')
        # Optional: Add index for faster date sorting later
        cursor.execute(f'''CREATE INDEX IF NOT EXISTS idx_published_at_iso ON {TABLE_NAME} (published_at_iso DESC);''') # Index descending
        conn.commit()
        print(f"Database '{DB_NAME}' initialized and table '{TABLE_NAME}' ensured.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

def insert_or_update_article(article_data):
    """Inserts a new article or updates an existing one based on URL."""
    conn = None
    required_keys = [
        "original_title", "source", "published_at", "article_description",
        "article_content", "article_url", "article_url_to_image",
        "historical_context", "glossary", "article_category", "llm_input_source",
        "llm_generated_title"
    ]
     # Ensure all required keys are present with default values if missing
    for key in required_keys:
         article_data.setdefault(key, None) # Use None as default for DB

    # Convert timeline and glossary lists/objects to JSON strings for SQLite storage
    hist_context = article_data.get("historical_context", [])
    gloss_context = article_data.get("glossary", [])
    try: historical_context_json = json.dumps(hist_context) if isinstance(hist_context, (list, dict)) else json.dumps([])
    except TypeError: historical_context_json = json.dumps([])
    try: glossary_json = json.dumps(gloss_context) if isinstance(gloss_context, (list, dict)) else json.dumps([])
    except TypeError: glossary_json = json.dumps([])

    # Format date for storage and potential sorting
    published_at_iso = None
    try:
        if article_data.get("published_at"):
             dt_obj = pd.to_datetime(article_data["published_at"], errors='coerce', utc=True)
             if pd.notna(dt_obj): published_at_iso = dt_obj.isoformat()
    except Exception as date_err: print(f"   Warn: Could not parse date '{article_data.get('published_at')}': {date_err}")

    # Use the original URL as the primary key
    article_url = article_data.get("article_url")
    if not article_url or article_url == '#':
         print(f"   Skipping DB insert - Invalid URL for article: {article_data.get('original_title', 'Unknown')[:50]}...")
         return False

    # Use ON CONFLICT for UPSERT (Update or Insert)
    sql = f'''
        INSERT INTO {TABLE_NAME} (
            original_url, original_title, llm_generated_title, source, published_at, published_at_iso,
            article_description, article_content, article_url_to_image,
            historical_context, glossary, article_category, llm_input_source, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(original_url) DO UPDATE SET
            original_title=excluded.original_title,
            llm_generated_title=excluded.llm_generated_title,
            source=excluded.source,
            published_at=excluded.published_at,
            published_at_iso=excluded.published_at_iso,
            article_description=excluded.article_description,
            article_content=excluded.article_content,
            article_url_to_image=excluded.article_url_to_image,
            historical_context=excluded.historical_context,
            glossary=excluded.glossary,
            article_category=excluded.article_category,
            llm_input_source=excluded.llm_input_source,
            last_updated=excluded.last_updated
    '''
    params = (
        article_url,
        article_data.get("original_title"),
        article_data.get("llm_generated_title"),
        article_data.get("source"),
        article_data.get("published_at"),
        published_at_iso,
        article_data.get("article_description"),
        article_data.get("article_content"),
        article_data.get("article_url_to_image"),
        historical_context_json, # Store JSON string
        glossary_json,           # Store JSON string
        article_data.get("article_category"),
        article_data.get("llm_input_source"),
        datetime.now().isoformat() # last_updated timestamp
    )

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        # print(f"   DB Success: {article_data.get('original_title')[:50]}...") # Keep console cleaner
        return True
    except sqlite3.Error as e:
        print(f"Database error inserting/updating article '{article_data.get('original_title')}': {e}")
        return False
    finally:
        if conn:
            conn.close()


# --- Helper: Fetch News ---
def fetch_news_articles(api_key, country="us"):
    """Fetches top headlines from NewsAPI."""
    if not api_key:
        print("NewsAPI key not available.")
        return []
    api_url = f"https://newsapi.org/v2/top-headlines?country={country}&apiKey={api_key}"
    print(f"Attempting NewsAPI fetch...")
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "ok": 
            articles_data = data.get("articles", [])
            print(f"NewsAPI fetch successful: {len(articles_data)} articles.")
            return articles_data
        else:
            print(f"NewsAPI Error: {data.get('message')}")
            return []
    except Exception as e: print(f"NewsAPI request error: {e}")
    return []

# --- Helper: Scrape News (newspaper3k) ---
def scrape_article_text_newspaper(url):
     """Scrapes article text using newspaper3k."""
     if not url or not url.startswith(('http://', 'https://')): return None
     print(f"Attempting newspaper3k scrape: {url[:80]}...")
     try:
        article = Article(url, fetch_images=False, request_timeout=20)
        article.download()
        if not article.html: 
            print("Scrape failed: HTML download error.")
            return None
        article.parse()
        scraped_text = article.text
        if scraped_text and scraped_text.strip():
            print(f"Scrape successful: ~{len(scraped_text)} chars.")
            return scraped_text
        else: 
            print("Scrape complete, no text extracted.")
            return None
     except Exception as e:
        print(f"Scrape error: {type(e).__name__} - {e}")
        return None

# --- Helper: Call OpenAI ---
def get_timeline_and_glossary(client: OpenAI, article_text: str, model_name: str = "gpt-4o"):
    """Calls OpenAI API to generate timeline, glossary, and category."""
    if not client:
        print("LLM Error: Client not configured.")
        return None
    if not article_text or not article_text.strip():
        print("LLM Error: Empty input.")
        return None
    prompt = meta_prompt.format(article_text)
    print(f"Calling OpenAI ({model_name})... ", end="")
    try:
        response = client.beta.chat.completions.parse(model=model_name, messages=[{"role": "user", "content": prompt}], response_format=OutputResponseFormat)
        if response.choices and response.choices[0].message and response.choices[0].message.parsed:
            parsed_output = response.choices[0].message.parsed
            print("Success.")
            return parsed_output
        else:
            finish_reason = response.choices[0].finish_reason if (response.choices and response.choices[0]) else 'N/A'
            print(f"Failed (No choices/parsed data. Finish: {finish_reason}).")
            return None
    except Exception as e:
         error_type = type(e).__name__ 
         details = str(e)
         if hasattr(e, 'status_code'):
            status_code = getattr(e, 'status_code', 'N/A')
            details = f"Status Code: {status_code}, Message: {details}"
         if hasattr(e, 'code'): 
            error_code = getattr(e, 'code', 'N/A')
            details += f", Code: {error_code}"
         print(f"Failed (Error Type: {error_type}, Details: {details})")
         return None

# ==============================================================================
# SECTION 4: MAIN PROCESSING LOGIC
# ==============================================================================
def process_and_store_articles():
    """Main function to fetch, process, and store articles in the DB."""
    print("\n--- Starting Article Processing & Storage ---")
    init_db() # Ensure DB and table exist

    raw_articles = fetch_news_articles(NEWS_API_KEY)
    if not raw_articles:
        print("No articles fetched. Stopping.")
        return

    total_articles = len(raw_articles)
    skipped_count = 0
    db_saved_count = 0
    print(f"Processing {total_articles} fetched articles...")
    print("="*60)

    for index, article_data in enumerate(raw_articles):
        print(f"\n--- Processing Article {index + 1} of {total_articles} ---")
        original_title=article_data.get('title','N/A')
        print(f"   Title: {original_title[:80]}...")
        description=article_data.get('description')
        content_snippet=article_data.get('content')
        source_name=article_data.get('source',{}).get('name','N/A')
        published_at=article_data.get('publishedAt','N/A')
        url=article_data.get('url','#')
        image_url=article_data.get('urlToImage')

        if not url or url == '#':
            skipped_count += 1
            print(f"   Skipping: Invalid URL.")
            continue

        # Determine content & scrape if needed
        scraped_full_text = scrape_article_text_newspaper(url)
        article_content_for_db = None
        text_for_llm = None
        source_used_for_llm = "None (Skipped)"

        if scraped_full_text:
            article_content_for_db = scraped_full_text
            text_for_llm = scraped_full_text
            source_used_for_llm = f"Scraped Text (~{len(scraped_full_text)} chars)"
        elif content_snippet and content_snippet.strip():
            article_content_for_db = content_snippet
            text_for_llm = content_snippet.split('[+')[0].strip()+"..." if '[+' in content_snippet else content_snippet
            source_used_for_llm = "API Content Snippet"
        elif description and description.strip():
            article_content_for_db = description
            text_for_llm = description
            source_used_for_llm = "API Description"
        else: 
            article_content_for_db = "Content unavailable."
            text_for_llm = None

        # Truncate LLM input if needed
        if text_for_llm and "Scraped Text" in source_used_for_llm:
             MAX_LLM_INPUT_CHARS = 15000
             if len(text_for_llm) > MAX_LLM_INPUT_CHARS:
                text_for_llm = text_for_llm[:MAX_LLM_INPUT_CHARS]
                print(f"   WARNING: Truncating LLM input.")

        # Call LLM
        if text_for_llm:
            output = get_timeline_and_glossary(openai_client, text_for_llm)
            if output:
                llm_category = getattr(output, 'article_category', 'Other')
                article_category = llm_category if llm_category in ALLOWED_CATEGORIES else "Other"
                if article_category != llm_category:
                    print(f"   Warn: LLM category '{llm_category}' invalid.")

                # Prepare data for DB, converting complex types
                timeline_list = [entry.model_dump() for entry in output.timeline_entries] if output.timeline_entries else []
                glossary_list = [entry.model_dump() for entry in output.glossary_entries] if output.glossary_entries else []

                db_data = {
                    "llm_generated_title": output.title_entry, "original_title": original_title,
                    "source": source_name, "published_at": published_at,
                    "article_description": description or "N/A",
                    "article_content": article_content_for_db, # Content for display
                    "article_url": url, "article_url_to_image": image_url,
                    "historical_context": timeline_list, # Pass list here
                    "glossary": glossary_list,           # Pass list here
                    "article_category": article_category,
                    "llm_input_source": source_used_for_llm
                }
                if insert_or_update_article(db_data): db_saved_count += 1
                else: skipped_count += 1 # Count failed DB inserts as skips
            else:
                skipped_count += 1
                print("   LLM processing failed. Skipping DB insert.")
        else:
             skipped_count += 1
             print("   No usable text for LLM. Skipping DB insert.")
        time.sleep(0.5) # Be polite to APIs/websites

    print("="*60)
    print(f"\n--- Article Processing Finished ---")
    print(f"DB Records Saved/Updated = {db_saved_count}, Skipped = {skipped_count}")

# --- Entry Point for Backend Script ---
if __name__ == "__main__":
    # No Streamlit commands here - this runs as a standard Python script
    if keys_valid: # Only run if keys were loaded okay
        process_and_store_articles()
    else:
        print("Backend script cannot run due to missing API keys in .env file.")

print("--- Backend Script Execution Finished ---")