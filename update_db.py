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
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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
  [A single paragraph of 3-4 sentences explaining: what happened, who the key players were (with necessary background about these people/groups), the situation at that time, and why these events occurred. Use language an average high school student can understand.]
  **[1-2 sentences explicitly connecting this historical event to the current news article.]**
    (Timeline Content Requirements: Focus only on relevant events, provide context, explain importance, use accessible language)

  3. **Glossary of Terms:** Include a section that defines any complex terms, jargon, or unfamiliar concepts mentioned in the article or timeline using extremely simple language.

  4. **Category Assignment:** Assign the single most relevant category to this article from the following list: {', '.join(ALLOWED_CATEGORIES)}. Output only the chosen category name.
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
def fetch_news_articles(api_key, from_date=None, to_date=None, country="us"):
    """Fetches news articles from NewsAPI for a specific date range."""
    if not api_key:
        print("NewsAPI key not available.")
        return []

    # Build the API URL with date parameters
    api_url = f"https://newsapi.org/v2/top-headlines?country={country}"
    if from_date and to_date:
        api_url += f"&from={from_date}&to={to_date}"
    api_url += f"&apiKey={api_key}"
    
    print(f"Fetching news for period: {from_date} to {to_date}")
    
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
    except Exception as e:
        print(f"NewsAPI request error: {e}")
        return []

# --- Helper: Scrape News (newspaper3k) ---
def scrape_article_text_newspaper(url):
    """Enhanced article scraping with multiple fallback methods."""
    if not url or not url.startswith(('http://', 'https://')):
        print(f"Invalid URL format: {url}")
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Attempting to scrape: {url[:80]}...")
    content = None

    # Method 1: Try newspaper3k first
    try:
        article = Article(url, fetch_images=False, request_timeout=20)
        article.download()
        if article.html:
            article.parse()
            content = article.text
            if content and len(content.strip()) > 200:  # Ensure meaningful content
                print(f"Successfully scraped with newspaper3k: ~{len(content)} chars")
                return content
            print("newspaper3k returned insufficient content, trying fallback...")
    except Exception as e:
        print(f"newspaper3k scraping failed: {type(e).__name__} - {e}")

    # Method 2: Direct BeautifulSoup scraping
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove unwanted elements
        for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'iframe']):
            tag.decompose()

        # Try common article content selectors
        content_selectors = [
            'article', 
            '[role="article"]',
            '.article-content',
            '.story-content',
            '.post-content',
            'main',
            '#main-content',
            '[itemprop="articleBody"]',
            '.entry-content'
        ]

        for selector in content_selectors:
            article_content = soup.select_one(selector)
            if article_content:
                # Extract paragraphs from the content area
                paragraphs = article_content.find_all('p')
                content = '\n\n'.join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 40)
                if content and len(content) > 200:
                    print(f"Successfully scraped with BeautifulSoup: ~{len(content)} chars")
                    return content

        # Method 3: Fallback to all paragraph extraction
        if not content:
            paragraphs = soup.find_all('p')
            content = '\n\n'.join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 40)
            if content and len(content) > 200:
                print(f"Successfully scraped using fallback method: ~{len(content)} chars")
                return content

    except Exception as e:
        print(f"BeautifulSoup scraping failed: {type(e).__name__} - {e}")

    # Method 4: Site-specific handlers for known problematic sites
    try:
        domain = urlparse(url).netloc
        if 'reuters.com' in domain:
            return scrape_reuters(soup)
        elif 'bloomberg.com' in domain:
            return scrape_bloomberg(soup)
        # Add more site-specific handlers as needed
    except Exception as e:
        print(f"Site-specific scraping failed: {type(e).__name__} - {e}")

    print("All scraping methods failed")
    return None

def scrape_reuters(soup):
    """Custom handler for Reuters articles."""
    paragraphs = soup.select('p.text__text__1FZLe')
    if not paragraphs:
        paragraphs = soup.select('.article-body p')
    content = '\n\n'.join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 40)
    return content if len(content) > 200 else None

def scrape_bloomberg(soup):
    """Custom handler for Bloomberg articles."""
    paragraphs = soup.select('.body-content p')
    if not paragraphs:
        paragraphs = soup.select('.body-copy p')
    content = '\n\n'.join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 40)
    return content if len(content) > 200 else None

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

def get_latest_db_date():
    """Gets the most recent published_at_iso date from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX(published_at_iso) FROM {TABLE_NAME}")
        result = cursor.fetchone()[0]
        if result:
            return pd.to_datetime(result).date()
        return None
    except Exception as e:
        print(f"Error getting latest date: {e}")
        return None
    finally:
        if conn:
            conn.close()

# ==============================================================================
# SECTION 4: MAIN PROCESSING LOGIC
# ==============================================================================
def clean_article_content(content):
    """Clean article content by removing '[+nnn chars]' pattern and formatting properly."""
    if not content or not isinstance(content, str):
        return None
    
    # Match pattern like '[+123 chars]' or '[+ 123 chars]' or similar variations
    import re
    cleaned_content = re.sub(r'\[\+\s*\d+\s*chars?\].*$', '', content, flags=re.IGNORECASE)
    
    # Clean up the result
    cleaned_content = cleaned_content.strip()
    
    # Add ellipsis if content was truncated
    if cleaned_content and cleaned_content != content:
        cleaned_content += "..."
    
    return cleaned_content if cleaned_content else None

def process_and_store_articles():
    """Main function to fetch, process, and store articles in the DB."""
    try:
        print("\n--- Starting Article Processing & Storage ---")
        init_db()

        # Get latest date and setup date range
        latest_db_date = get_latest_db_date()
        start_date = (latest_db_date + timedelta(days=1)) if latest_db_date else (datetime.now().date() - timedelta(days=30))
        current_date = datetime.now().date()
        total_articles_saved = 0
        
        result = {
            'success': False,
            'articles_saved': 0,
            'dates_processed': [],
            'articles_per_date': {},
            'errors': []
        }

        while start_date <= current_date:
            print(f"\nProcessing date: {start_date}")
            from_date = start_date.isoformat()
            to_date = (start_date + timedelta(days=1)).isoformat()
            raw_articles = fetch_news_articles(NEWS_API_KEY, from_date, to_date)
            
            daily_count = 0
            
            if not raw_articles:
                result['dates_processed'].append(start_date.isoformat())
                result['articles_per_date'][start_date.isoformat()] = 0
                start_date += timedelta(days=1)
                continue

            for index, article_data in enumerate(raw_articles):
                print(f"\n--- Processing Article {index + 1} of {len(raw_articles)} ---")
                
                # Get basic article info
                url = article_data.get('url')
                if not url or url == '#':
                    result['errors'].append(f"Invalid URL for article on {start_date}")
                    continue

                # Get article content in order of priority
                article_content = None
                content_source = "None"

                # Enhanced content retrieval with retries
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    article_content = scrape_article_text_newspaper(url)
                    if article_content and len(article_content) > 200:
                        break
                    if attempt < max_retries - 1:
                        print(f"Retry {attempt + 1}/{max_retries} after {retry_delay}s...")
                        time.sleep(retry_delay)

                # Fallback to API content if scraping failed
                if not article_content:
                    if article_data.get('content'):
                        article_content = clean_article_content(article_data['content'])
                    elif article_data.get('description'):
                        article_content = article_data['description']

                if not article_content:
                    result['errors'].append(f"No content available for {url}")
                    continue

                # Prepare text for LLM
                text_for_llm = article_content
                if len(text_for_llm) > 15000:
                    text_for_llm = text_for_llm[:15000] + "..."

                # Process with LLM
                if text_for_llm:
                    output = get_timeline_and_glossary(openai_client, text_for_llm)
                    if output:
                        db_data = {
                            "llm_generated_title": output.title_entry,
                            "original_title": article_data.get('title', 'N/A'),
                            "source": article_data.get('source', {}).get('name', 'N/A'),
                            "published_at": article_data.get('publishedAt', 'N/A'),
                            "article_content": article_content,  # Store cleaned content
                            "article_url": url,
                            "article_url_to_image": article_data.get('urlToImage'),
                            "historical_context": [entry.model_dump() for entry in output.timeline_entries],
                            "glossary": [entry.model_dump() for entry in output.glossary_entries],
                            "article_category": getattr(output, 'article_category', 'Other'),
                            "content_source": content_source
                        }
                        
                        if insert_or_update_article(db_data):
                            daily_count += 1
                            total_articles_saved += 1

            result['dates_processed'].append(start_date.isoformat())
            result['articles_per_date'][start_date.isoformat()] = daily_count
            start_date += timedelta(days=1)
            time.sleep(1)  # Rate limiting between dates

        result['success'] = total_articles_saved > 0
        result['articles_saved'] = total_articles_saved
        
        print("="*60)
        print(f"\n--- Article Processing Finished ---")
        print(f"Total new articles saved: {total_articles_saved}")
        
        return total_articles_saved > 0

    except Exception as e:
        print(f"Error in process_and_store_articles: {str(e)}")
        return False

# --- Entry Point for Backend Script ---
if __name__ == "__main__":
    # No Streamlit commands here - this runs as a standard Python script
    if keys_valid: # Only run if keys were loaded okay
        process_and_store_articles()
    else:
        print("Backend script cannot run due to missing API keys in .env file.")

print("--- Backend Script Execution Finished ---")
