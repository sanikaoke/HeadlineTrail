import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
# Then use it securely

# ==============================================================================
# SECTION 1: SETUP & IMPORTS
# ==============================================================================

import requests, pandas as pd, json, os, time
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from bs4 import BeautifulSoup
from newspaper import Article, ArticleException # Import newspaper3k
print("Libraries installed and imported.")

# ==============================================================================
# SECTION 2: API KEY CONFIGURATION (HARDCODED - NOT RECOMMENDED FOR PRODUCTION)
# ==============================================================================
print("\n--- Section 2: API Key Configuration ---")

openai_client = None
if NEWS_API_KEY and OPENAI_API_KEY and "YOUR_ACTUAL_OPENAI_API_KEY" not in OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("API Keys found. OpenAI client configured successfully.")
    except Exception as e:
        print(f"Error configuring OpenAI client: {e}")
        openai_client = None
else:
    print("API keys missing or placeholder detected.")
    openai_client = None

# ==============================================================================
# SECTION 3: FETCH LIVE NEWS ARTICLES FROM NEWSAPI
# ==============================================================================
print("\n--- Section 3: Fetch Live News Articles ---")
country_code = "us"

def fetch_news_articles(api_key, country):
    """Fetches top headlines from NewsAPI for a given country."""
    if not api_key:
        print("NewsAPI key is missing in the code. Cannot fetch articles.")
        return []
    api_url = f"https://newsapi.org/v2/top-headlines?country={country}&apiKey={api_key}"
    print(f"Attempting to fetch news articles from {api_url.split('apiKey=')[0]}...") # Hide key
    articles_data = []
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "ok":
            articles_data = data.get("articles", [])
            print(f"Successfully fetched {len(articles_data)} articles.")
            return articles_data
        else:
            print(f"NewsAPI Error: Status={data.get('status')}, Code={data.get('code')}, Message={data.get('message')}")
            return []
    except requests.exceptions.Timeout:
        print("Error: The request to NewsAPI timed out.")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred during NewsAPI request: {http_err}")
        if http_err.response is not None:
             print(f"Response Status Code: {http_err.response.status_code}")
             try: print(f"Response Body: {http_err.response.json()}")
             except json.JSONDecodeError: print(f"Response Body (non-JSON): {http_err.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error during NewsAPI request: {e}")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON response from NewsAPI.")
        if 'response' in locals() and response is not None: print(f"Response Text: {response.text}")
    return articles_data # Return empty list if any error occurs

all_fetched_articles = []
if NEWS_API_KEY:
    all_fetched_articles = fetch_news_articles(NEWS_API_KEY, country_code)

articles_to_process = all_fetched_articles

if articles_to_process:
    print(f"\nWill attempt to process all {len(articles_to_process)} fetched article(s).")
else:
    print("\nNo live articles fetched. Exiting.")
    # Optional: exit here if needed
    # import sys
    # sys.exit()

# ==============================================================================
# SECTION 4: DEFINE PROMPT, PYDANTIC MODELS, SCRAPING (newspaper3k) & HELPER FUNCTIONS
# ==============================================================================
print("\n--- Section 4: Define Prompt, Pydantic Models, Scraping (newspaper3k) & Helper Functions ---")

# (Pydantic Models Definition)
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
print("Pydantic models defined.")

# (Meta Prompt Definition - COMPLETE VERSION)
meta_prompt = """Given a news article, create a comprehensive historical timeline that provides readers with the essential background needed to fully understand the current event.

Here's the news article:
{}

Output

  1. Based on the news article, come up with a relevant title for the article.

  2. **Historical Context Timeline** - Create a chronological timeline of the key historical events that directly contribute to understanding the current news article. Format each entry as:

  **[YEAR/PERIOD] - [BRIEF DESCRIPTIVE HEADLINE]**
  [A single paragraph of 4-6 sentences explaining: what happened, who the key players were (with necessary background about these people/groups), the situation at that time, and why these events occurred. Use language an average high school student can understand.]
  *[1-2 sentences explicitly connecting this historical event to the current news article.]*

    Timeline Content Requirements:
      - Focus only on events directly relevant to understanding the current article
      - Provide sufficient context about key players and circumstances
      - Explain why each historical event matters to the current situation
      - Use accessible language that assumes no prior knowledge of the topic

  3. **Glossary of Terms**
      Include a section that:
      - Defines any complex terms, jargon, or unfamiliar concepts mentioned in the article or timeline
      - Uses extremely simple language for each definition"""
print("Meta prompt defined.")

# (Web Scraping Function using newspaper3k - COMPLETE VERSION)
def scrape_article_text_newspaper(url):
    """Attempts to scrape the main article text from a URL using newspaper3k."""
    if not url or not url.startswith(('http://', 'https://')):
        print("   Skipping scraping: Invalid URL provided.")
        return None

    print(f"   Attempting to scrape using newspaper3k: {url[:80]}...")
    try:
        # Configure newspaper Article object
        article = Article(url, fetch_images=False, request_timeout=20) # Increased timeout
        # Set a more generic user-agent (optional, sometimes helps)
        # article.headers = {'User-Agent': 'Mozilla/5.0'}
        article.download()
        # Check if download was successful
        if not article.html:
             print("   newspaper3k scraping error: Failed to download HTML content (could be blocked, timeout, or bad URL).")
             return None
        article.parse()

        scraped_text = article.text
        if scraped_text and scraped_text.strip():
            print(f"   Successfully scraped ~{len(scraped_text)} characters with newspaper3k.")
            return scraped_text
        else:
            print("   newspaper3k parsing completed, but no text was extracted (possibly dynamic content or unusual structure).")
            return None
    except ArticleException as e:
        # Specific newspaper3k exception
        print(f"   newspaper3k scraping error (ArticleException): {e}")
        return None
    except Exception as e:
        # Catch other potential errors (network, timeouts etc.)
        error_type = type(e).__name__
        print(f"   newspaper3k scraping error (Type: {error_type}, Details: {e})")
        return None
print("Newspaper3k scraping function defined.")

# (Helper Function Definition for OpenAI - COMPLETE VERSION with enhanced errors)
def get_timeline_and_glossary(client: OpenAI, article_text: str, model_name: str = "gpt-4o"):
    """Calls OpenAI API to generate timeline and glossary using structured output."""
    if not client:
        print("   ERROR: OpenAI client not configured.")
        return None
    if not article_text or not article_text.strip():
        print("   ERROR: Article text is empty for LLM input.")
        return None

    # Ensure the meta_prompt is correctly formatted with the article text
    prompt = meta_prompt.format(article_text)

    print(f"   Calling OpenAI API ({model_name})... ", end="")
    try:
        # Make the API call using the client's method for structured parsing
        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt},
            ],
            response_format=OutputResponseFormat # Use the Pydantic model
        )

        # Check if the response has choices and parsed data
        if response.choices and response.choices[0].message and response.choices[0].message.parsed:
             parsed_output = response.choices[0].message.parsed
             print("Success.")
             return parsed_output
        else:
             finish_reason = response.choices[0].finish_reason if (response.choices and response.choices[0]) else 'N/A'
             print(f"Failed (No choices or parsed data in response. Finish Reason: {finish_reason}).")
             # print(f"Raw Response Content: {response}") # Uncomment for deep debugging
             return None

    # Enhanced Error Handling
    except Exception as e:
         error_type = type(e).__name__
         details = str(e)
         # Attempt to extract more specific details from OpenAI errors
         if hasattr(e, 'status_code'): # Check for status code if it's an APIError
              details = f"Status Code: {e.status_code}, Message: {details}"
         if hasattr(e, 'code'): # Check for specific error code from OpenAI
              details += f", Code: {e.code}"

         print(f"Failed (Error Type: {error_type}, Details: {details})")
         # import traceback # Uncomment for deep debugging
         # print(traceback.format_exc()) # Uncomment for deep debugging
         return None
print("OpenAI helper function defined.")


# ==============================================================================
# SECTION 5: PROCESS ARTICLES, SCRAPE FIRST, FALLBACK FOR CONTENT, SKIP IF NO CONTENT
# ==============================================================================
print("\n--- Section 5: Process Articles, Scrape First, Fallback for Content, Skip if No Content ---")

results_for_csv = []

if not articles_to_process:
    print("Skipping processing as no articles were fetched.")
elif not openai_client:
    print("Skipping processing as OpenAI client is not configured.")
else:
    total_articles = len(articles_to_process)
    skipped_count = 0
    processed_count = 0
    print(f"\nProcessing up to {total_articles} fetched article(s)...")
    print("!!! WARNING: Will attempt to scrape ALL websites AND call OpenAI API.")
    print("!!! Check costs, time, rate limits, and website ToS.")
    print("="*80)

    for index, article_data in enumerate(articles_to_process):
        print(f"\n--- Processing Article {index + 1} of {total_articles} ---")
        print(f"   Title: {article_data.get('title', 'N/A')[:80]}...")

        # 1. EXTRACT INITIAL DETAILS
        original_title = article_data.get('title', 'N/A')
        description = article_data.get('description')
        content_snippet = article_data.get('content')
        source_name = article_data.get('source', {}).get('name', 'N/A')
        published_at = article_data.get('publishedAt', 'N/A')
        url = article_data.get('url', '#')
        image_url = article_data.get('urlToImage')

        # --- 2. SCRAPE & DETERMINE FINAL CONTENT FOR CSV & LLM INPUT ---
        scraped_full_text = scrape_article_text_newspaper(url) # Always attempt scraping
        article_content_for_csv = None # Holds best text for display
        text_for_llm = None          # Holds (maybe truncated) text for LLM
        source_used_for_llm = "None (Skipped)" # Default status

        if scraped_full_text:
            # Scraping succeeded
            article_content_for_csv = scraped_full_text
            text_for_llm = scraped_full_text # Use full text for LLM initially
            source_used_for_llm = f"Scraped Text (newspaper3k - {len(scraped_full_text)} chars)"
            print(f"   Scraping successful. Using {source_used_for_llm} for display and LLM base.")

        elif content_snippet and content_snippet.strip():
            # Scraping failed - fallback 1: use API content snippet
            article_content_for_csv = content_snippet
            # Clean snippet for LLM
            if '[+' in content_snippet and ' chars]' in content_snippet:
                 content_snippet_cleaned = content_snippet.split('[+')[0].strip() + "..."
            else:
                 content_snippet_cleaned = content_snippet
            text_for_llm = content_snippet_cleaned
            source_used_for_llm = "API Content Snippet"
            print(f"   Scraping failed. Using {source_used_for_llm} for display and LLM.")

        elif description and description.strip():
            # Scraping & snippet failed - fallback 2: use API description
            article_content_for_csv = description
            text_for_llm = description
            source_used_for_llm = "API Description"
            print(f"   Scraping failed. Using {source_used_for_llm} for display and LLM.")

        else:
            # All failed - Article will be skipped
            article_content_for_csv = "Content unavailable (Scraping failed and no API content/description)."
            print(f"   {article_content_for_csv}") # Print reason for skipping
            text_for_llm = None # Ensure LLM step is skipped

        # --- Optional: Truncate LLM input if it came from scraping and is too long ---
        if text_for_llm and "Scraped Text" in source_used_for_llm:
             MAX_LLM_INPUT_CHARS = 15000 # Example limit - adjust based on model/needs
             if len(text_for_llm) > MAX_LLM_INPUT_CHARS:
                 print(f"   WARNING: Truncating scraped text from {len(text_for_llm)} to {MAX_LLM_INPUT_CHARS} chars for LLM input.")
                 text_for_llm = text_for_llm[:MAX_LLM_INPUT_CHARS]


        # --- 3. GENERATE TIMELINE/GLOSSARY (ONLY IF text_for_llm is valid) ---
        if text_for_llm: # Check if we have *any* usable text for the LLM
            output = get_timeline_and_glossary(openai_client, text_for_llm)

            if output:
                # --- 4. COLLECT FOR CSV (Only if LLM call succeeded) ---
                generated_title = output.title_entry
                timeline_text_parts = [f"[{e.year}] - {e.title}\n{e.summary}" for e in output.timeline_entries] if output.timeline_entries else []
                timeline_for_csv = "\n\n".join(timeline_text_parts) if timeline_text_parts else "No timeline entries generated."
                glossary_text_parts = [f"{g.word}: {g.definition}" for g in output.glossary_entries] if output.glossary_entries else []
                glossary_for_csv = "\n".join(glossary_text_parts) if glossary_text_parts else "No glossary entries generated."

                results_for_csv.append({
                    "llm_generated_title": generated_title,
                    "original_title": original_title,
                    "source": source_name,
                    "published_at": published_at,
                    "article_description": description if description else "N/A", # Still save original desc
                    "article_content": article_content_for_csv, # Holds scraped/API text/status for display
                    "article_url": url,
                    "article_url_to_image": image_url if image_url else None,
                    "historical_context": timeline_for_csv,
                    "glossary": glossary_for_csv,
                    "llm_input_source": source_used_for_llm
                })
                print("   Collected results for CSV.")
                processed_count += 1
            else:
                # LLM call failed - don't save this article row
                print("   Skipping article: Failed to generate timeline/glossary (OpenAI call failed).")
                skipped_count += 1
        else:
            # This case means all content sources failed before the LLM step
            print("   Skipping article: No usable text source found for LLM input.")
            skipped_count += 1


        # --- Optional Delay ---
        print(f"--- Pausing for 1 second ---")
        time.sleep(1)


# ==============================================================================
# SECTION 6: SAVE RESULTS TO CSV
# ==============================================================================
print("\n--- Section 6: Save Results to CSV ---")

print(f"\nProcessing Summary: Processed and Saved = {processed_count}, Skipped = {skipped_count}")

if results_for_csv:
    try:
        final_df = pd.DataFrame(results_for_csv)
        csv_filename = "live_articles_with_context.csv"
        print(f"DEBUG: Columns being saved: {final_df.columns.tolist()}") # Verify columns
        final_df.to_csv(csv_filename, index=False, encoding='utf-8')
        print(f"\nSuccessfully saved {len(results_for_csv)} processed articles to '{csv_filename}'")
        print("\n--- Sample of Saved Data (first 5 rows) ---")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(final_df.head())
        print("-" * 50)
    except Exception as e:
        print(f"Error saving results to CSV: {e}")
else:
    print("No results were successfully processed to save to CSV.")

print("\n--- Script Finished ---")