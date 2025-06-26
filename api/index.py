# backend_api.py (Handles data retrieval and filtering)
import sqlite3
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
from dotenv import load_dotenv
#from update_db import process_and_store_articles

print("--- Backend API Starting ---")

# --- Database Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "news_data.db" 
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
TABLE_NAME = "articles"
print(f"Using database at: {DB_PATH}")

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) 
print("Flask app created and CORS enabled.")

# --- Constants ---
IMAGE_COLUMN_NAME = "article_url_to_image"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80"

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
    if not date_obj: return "Unknown Date"
    try:
        # Convert to timezone-naive if necessary
        if date_obj.tzinfo is not None: date_obj = date_obj.astimezone(None)
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
# --- DIAGNOSTIC TEST FUNCTION ---
def query_articles(filters):
    print("--- RUNNING DIAGNOSTIC TEST ---")
    conn = get_db_connection()
    if conn is None:
        # Create a fake article to display the connection error
        return [{
            "original_title": "DIAGNOSTIC: DATABASE CONNECTION FAILED",
            "source": "Please check Vercel Environment Variables for TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.",
            "article_url_to_image": "", "published_at_formatted": "Now"
        }]

    try:
        cursor = conn.cursor()
        # Ask the database for a simple count of articles
        cursor.execute("SELECT COUNT(*) FROM articles;")
        count = cursor.fetchone()[0]
        conn.close()

        # Create a single "fake" article to display the result
        print(f"--- DIAGNOSTIC: Database has {count} articles. ---")
        return [{
            "original_title": f"DIAGNOSTIC: Found {count} Articles in Database",
            "source": "This confirms Vercel can connect and count.",
            "article_url_to_image": "", "published_at_formatted": "Now"
        }]
    except Exception as e:
        # Create a fake article to display a query error
        print(f"--- DIAGNOSTIC: QUERY FAILED: {e} ---")
        return [{
            "original_title": "DIAGNOSTIC: DATABASE QUERY FAILED",
            "source": f"The error was: {e}",
            "article_url_to_image": "", "published_at_formatted": "Now"
        }]

# --- API Endpoint for Articles ---
@app.route('/articles', methods=['GET'])
def get_articles():
    """Endpoint to fetch articles, accepts filter params."""
    print("\nReceived request for /articles")
    search_query = request.args.get('search', default=None, type=str)
    sort_option = request.args.get('sort', default="Newest First", type=str)
    selected_month = request.args.get('month', default="All Months", type=str)
    selected_day = request.args.get('day', default="All Days", type=str)
    selected_category = request.args.get('category', default="All Categories", type=str)

    print(f"Filters received: Search='{search_query}', Sort='{sort_option}', Category='{selected_category}', Month='{selected_month}', Day='{selected_day}'")
    filters = {
        'search': search_query,
        'category': selected_category,
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
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500

    options = {
        "categories": ["All Categories"],
        "months": ["All Months"],
        "days_by_month": {"All Months": ["All Days"]},
        "all_unique_days": ["All Days"]
    }
    try:
        cursor = conn.cursor()
        
        # Get categories
        cursor.execute(f"SELECT DISTINCT article_category FROM {TABLE_NAME} WHERE article_category IS NOT NULL AND article_category != '' AND article_category != 'N/A'")
        cats = [row[0] for row in cursor.fetchall() if row[0] is not None]
        options["categories"].extend(sorted(list(set(cats))))

        # Get dates
        cursor.execute(f"SELECT DISTINCT published_at_iso FROM {TABLE_NAME} WHERE published_at_iso IS NOT NULL AND published_at_iso != ''")
        dates_str = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if dates_str:
            all_dates = []
            for date_s in dates_str:
                try:
                    if date_s.endswith('Z'):
                       date_s = date_s[:-1] + '+00:00'
                    all_dates.append(datetime.fromisoformat(date_s))
                except (ValueError, TypeError):
                    continue
            
            if all_dates:
                # Create unique Year-Month strings and sort them descending
                year_month_strs = sorted(list(set([d.strftime('%Y - %B') for d in all_dates])), key=lambda d: datetime.strptime(d, '%Y - %B'), reverse=True)
                options["months"].extend(year_month_strs)
                
                # Group days by month
                days_by_month_dict = {}
                for d in all_dates:
                    ym_str = d.strftime('%Y - %B')
                    if ym_str not in days_by_month_dict:
                        days_by_month_dict[ym_str] = set()
                    days_by_month_dict[ym_str].add(str(d.day))

                for ym_str, days_set in days_by_month_dict.items():
                    options["days_by_month"][ym_str] = ["All Days"] + sorted(list(days_set), key=int)
                
                # Get all unique days across the entire dataset
                all_unique_days = sorted(list(set([str(d.day) for d in all_dates])), key=int)
                options["all_unique_days"].extend(all_unique_days)

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
    # This feature is disabled on the live deployment to avoid timeouts 
    # and dependencies. It should be run manually.
    print("Fetch Latest News endpoint called, but is disabled on live deployment.")
    return jsonify({
        'success': False, 
        'message': 'This feature is disabled on the live version and must be run manually.'
    }), 403
# --- Run the Flask App ---
if __name__ == '__main__':
    print("Starting Flask development server on http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
