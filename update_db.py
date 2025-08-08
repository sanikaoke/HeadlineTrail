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
from typing import List
from newspaper import Article
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse

print("Libraries imported.")

# ==============================================================================
# API KEY CONFIGURATION & CLIENT INITIALIZATION
# ==============================================================================
print("Loading API keys from .env file...")
load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = None
keys_valid = True
if NEWS_API_KEY and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client configured successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR configuring OpenAI client: {e}")
        keys_valid = False
else:
    missing_keys = []
    if not NEWS_API_KEY: missing_keys.append("NewsAPI Key")
    if not OPENAI_API_KEY: missing_keys.append("OpenAI Key")
    print(f"CRITICAL API Key Error: Missing {', '.join(missing_keys)} in .env file.")
    keys_valid = False

if not keys_valid:
    exit()

# ==============================================================================
# DEFINITIONS
# ==============================================================================

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
    summarized_bullets: List[str]

ALLOWED_CATEGORIES = [
    "Politics", "Business", "Technology", "Health", "Science", "Sports",
    "Entertainment", "World News", "US News", "Other"
]

meta_prompt = f"""Given a news article, perform the following tasks:

Here's the news article:
{{}}

Output

1) **Title:** Provide a concise, informative headline for the article.

2) **Historical Context Timeline:** Create a chronological timeline, strictly ascending years, of the key historical events that directly contribute to understanding the current news article. Format each entry as:
**[YEAR/PERIOD] - [BRIEF DESCRIPTIVE HEADLINE]**
[A single paragraph of 3–4 sentences explaining: what happened, who the key players were, the situation at that time, and why these events occurred.]
**[Add 1–2 sentences explicitly connecting this historical event to the current news article.]**

3) **Glossary of Terms:** Define any complex terms or jargon using extremely simple language.

4) **Category Assignment:** Assign one category from: {', '.join(ALLOWED_CATEGORIES)}.

5) **Scan-friendly Summary Bullets:** Summarize the article into ≤5 bullets:
   - 1 sentence per bullet; ≤18 words per bullet.
   - Final bullet starts with “Why it matters:” and states the significance.
"""

DB_NAME = "news_data.db"
TABLE_NAME = "articles"

def init_db():
    """Initialize DB & ensure summarized_content column exists."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            original_url TEXT PRIMARY KEY NOT NULL,
            original_title TEXT,
            llm_generated_title TEXT,
            author TEXT,
            source TEXT,
            published_at TEXT,
            published_at_iso TEXT,
            article_description TEXT,
            article_content TEXT,
            summarized_content TEXT,
            article_url_to_image TEXT,
            historical_context TEXT,
            glossary TEXT,
            article_category TEXT,
            llm_input_source TEXT,
            last_updated TEXT
        )
    ''')
    # Ensure summarized_content column exists
    cursor.execute(f"PRAGMA table_info({TABLE_NAME});")
    cols = [row[1] for row in cursor.fetchall()]
    if "summarized_content" not in cols:
        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN summarized_content TEXT;")
        print("Added missing column: summarized_content")
    conn.commit()
    conn.close()

def insert_or_update_article(article_data):
    hist_context = json.dumps(article_data.get("historical_context", []))
    gloss_context = json.dumps(article_data.get("glossary", []))
    published_at_iso = None
    if article_data.get("published_at"):
        dt_obj = pd.to_datetime(article_data["published_at"], errors='coerce', utc=True)
        if pd.notna(dt_obj):
            published_at_iso = dt_obj.isoformat()

    sql = f'''
        INSERT INTO {TABLE_NAME} (
            original_url, original_title, llm_generated_title, author, source,
            published_at, published_at_iso,
            article_description, article_content, summarized_content, article_url_to_image,
            historical_context, glossary, article_category, llm_input_source, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(original_url) DO UPDATE SET
            original_title=excluded.original_title,
            llm_generated_title=excluded.llm_generated_title,
            author=excluded.author,
            source=excluded.source,
            published_at=excluded.published_at,
            published_at_iso=excluded.published_at_iso,
            article_description=excluded.article_description,
            article_content=excluded.article_content,
            summarized_content=excluded.summarized_content,
            article_url_to_image=excluded.article_url_to_image,
            historical_context=excluded.historical_context,
            glossary=excluded.glossary,
            article_category=excluded.article_category,
            llm_input_source=excluded.llm_input_source,
            last_updated=excluded.last_updated
    '''
    params = (
        article_data.get("article_url"),
        article_data.get("original_title"),
        article_data.get("llm_generated_title"),
        article_data.get("author"),
        article_data.get("source"),
        article_data.get("published_at"),
        published_at_iso,
        article_data.get("article_description"),
        article_data.get("article_content"),
        article_data.get("summarized_content"),
        article_data.get("article_url_to_image"),
        hist_context,
        gloss_context,
        article_data.get("article_category"),
        article_data.get("llm_input_source"),
        datetime.now().isoformat()
    )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()
    return True

def summarize_article_content(article_text: str):
    """Generate ≤5 bullet summary; fallback to full article_content."""
    summary_prompt = f"""
Summarize the article below into ≤5 bullets a reader can scan in under a minute.

Rules:
- 1 sentence per bullet; ≤18 words each.
- Final bullet starts with 'Why it matters:' and states significance.

Article:
{article_text}
"""
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summary generation failed: {e}")
        return article_text  # fallback

def fetch_news_articles(api_key, from_date, to_date, search_query="news"):
    excluded = (
        "wsj.com,nytimes.com,ft.com,bloomberg.com,economist.com,latimes.com,"
        "washingtonpost.com,businessinsider.com,theathletic.com,newyorker.com,"
        "thetimes.co.uk,financialpost.com,lemonde.fr,telegraph.co.uk,irishtimes.com,"
        "sueddeutsche.de,handelsblatt.com,nzz.ch,chron.com,bostonglobe.com"
    )
    api_url = (
        f"https://newsapi.org/v2/everything?"
        f"q={search_query}&language=en&from={from_date}&to={to_date}&"
        f"sortBy=popularity&excludeDomains={excluded}&pageSize=100&apiKey={api_key}"
    )
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "ok":
            return data.get("articles", [])
        return []
    except Exception as e:
        print(f"NewsAPI request error: {e}")
        return []

def scrape_article_text_newspaper(url):
    try:
        article = Article(url, fetch_images=False)
        article.download()
        article.parse()
        if article.text and len(article.text) > 200:
            return article.text
    except:
        pass
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = "\n\n".join(p.get_text().strip() for p in paragraphs)
        if len(content) > 200:
            return content
    except:
        pass
    return None

def get_timeline_and_glossary(article_text: str):
    prompt = meta_prompt.format(article_text)
    try:
        resp = openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format=OutputResponseFormat
        )
        return resp.choices[0].message.parsed
    except Exception as e:
        print(f"LLM processing failed: {e}")
        return None

# ==============================================================================
# MAIN PROCESS
# ==============================================================================
def process_and_store_articles():
    init_db()
    total_articles_saved = 0

    raw_articles = fetch_news_articles(NEWS_API_KEY, "2025-07-20", "2025-08-06")
    for article_data in raw_articles:
        url = article_data.get("url")
        if not url:
            continue
        article_content = scrape_article_text_newspaper(url) or article_data.get("content") or article_data.get("description")
        if not article_content:
            continue

        output = get_timeline_and_glossary(article_content)
        summary = summarize_article_content(article_content) if article_content else None
        if not summary:
            summary = article_content

        if output:
            db_data = {
                "llm_generated_title": output.title_entry,
                "original_title": article_data.get("title", "N/A"),
                "author": article_data.get("author", "N/A"),
                "source": article_data.get("source", {}).get("name", "N/A"),
                "published_at": article_data.get("publishedAt", "N/A"),
                "article_content": article_content,
                "summarized_content": summary,
                "article_url": url,
                "article_url_to_image": article_data.get("urlToImage"),
                "historical_context": [e.model_dump() for e in output.timeline_entries],
                "glossary": [e.model_dump() for e in output.glossary_entries],
                "article_category": getattr(output, "article_category", "Other"),
                "llm_input_source": "scraper"
            }
            insert_or_update_article(db_data)
            total_articles_saved += 1

    print(f"Total new articles saved: {total_articles_saved}")

if __name__ == "__main__":
    if keys_valid:
        process_and_store_articles()

print("--- Backend Script Execution Finished ---")
