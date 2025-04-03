import streamlit as st
import pandas as pd
import math
from datetime import datetime

# --- Configuration ---
CSV_FILE_PATH = "live_articles_with_context.csv"
IMAGE_COLUMN_NAME = "article_url_to_image"
ARTICLE_CONTENT_COLUMN = "article_content"
DEFAULT_IMAGE = "https://via.placeholder.com/300x200.png?text=No+Image"
ARTICLES_PER_ROW = 3

# --- Helper Function to Load Data (with Caching) ---
@st.cache_data
def load_data(file_path):
    """Loads the CSV data into a Pandas DataFrame."""
    try:
        df = pd.read_csv(file_path)

        # Ensure image column exists and fill missing
        if IMAGE_COLUMN_NAME not in df.columns:
            st.warning(f"Image column '{IMAGE_COLUMN_NAME}' not found in CSV. Using placeholders.")
            df[IMAGE_COLUMN_NAME] = DEFAULT_IMAGE
        else:
            df[IMAGE_COLUMN_NAME].fillna(DEFAULT_IMAGE, inplace=True)
            df[IMAGE_COLUMN_NAME] = df[IMAGE_COLUMN_NAME].replace('', DEFAULT_IMAGE)

        # Ensure article content column exists and fill missing
        if ARTICLE_CONTENT_COLUMN not in df.columns:
            st.warning(f"Article content column '{ARTICLE_CONTENT_COLUMN}' not found in CSV.")
            df[ARTICLE_CONTENT_COLUMN] = "Content not available."

        # Handle other potential missing values including the content column
        df.fillna({
            "llm_generated_title": "Untitled", 
            "original_title": "Untitled",
            "source": "Unknown Source", 
            "published_at": "Unknown Date",
            "article_description": "No description available.",
            ARTICLE_CONTENT_COLUMN: "Content not available.",
            "article_url": "#",
            "historical_context": "No historical context available.",
            "glossary": "No glossary terms available.",
        }, inplace=True)

        # Convert published_at to datetime
        try:
            df['published_at_dt'] = pd.to_datetime(df['published_at'], errors='coerce')
            df = df.sort_values(by='published_at_dt', ascending=False).reset_index(drop=True)
        except Exception:
            st.warning("Could not parse 'published_at' column as dates.")
            df['published_at_dt'] = None

        return df
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        st.error(f"An error occurred while loading the CSV file: {e}")
        return None

# --- Apply basic styling using Streamlit's native methods ---
def setup_page_styling():
    # Set page config first before any other Streamlit commands
    st.set_page_config(
        page_title="HeadlineTrail",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Apply some basic CSS that won't interfere with Streamlit's rendering
    st.markdown("""
        <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1 {
            color: #1E88E5;
        }
        </style>
    """, unsafe_allow_html=True)

# --- Helper Functions for Display ---
def format_date(date_obj):
    """Format date in a readable way with relative time indicator."""
    if not date_obj or pd.isna(date_obj):
        return "Unknown Date"
    
    try:
        now = datetime.now()
        delta = now - date_obj
        
        if delta.days == 0:
            return f"Today, {date_obj.strftime('%B %d, %Y')}"
        elif delta.days == 1:
            return f"Yesterday, {date_obj.strftime('%B %d, %Y')}"
        elif delta.days < 7:
            return f"{delta.days} days ago, {date_obj.strftime('%B %d, %Y')}"
        else:
            return date_obj.strftime('%B %d, %Y')
    except:
        return str(date_obj)

def display_article_card(article_data, index):
    """Displays a single article card with basic styling."""
    with st.container():
        with st.container():
            # Card with border
            with st.expander("", expanded=True):
                # Image
                image_display_url = article_data.get(IMAGE_COLUMN_NAME, DEFAULT_IMAGE)
                if not isinstance(image_display_url, str) or not image_display_url.startswith(('http://', 'https://')):
                    image_display_url = DEFAULT_IMAGE
                st.image(image_display_url, use_container_width=True)
                
                # Title
                title_to_display = article_data.get("original_title", article_data.get("llm_generated_title", "Untitled"))
                st.subheader(title_to_display)
                
                # Source and date
                date_str = article_data.get("published_at", "Unknown Date")
                if pd.notna(article_data.get('published_at_dt')):
                    date_str = article_data['published_at_dt'].strftime('%B %d, %Y')
                source = article_data.get('source', 'Unknown Source')
                st.caption(f"📰 {source} • 📅 {date_str}")
                
                # Description preview
                description = article_data.get('article_description', 'No description available.')
                st.write(description)
                
                # Read more button
                if st.button("Read More →", key=f"read_more_{index}", use_container_width=True):
                    st.session_state.selected_article_index = index
                    st.rerun()

def display_article_detail(article_data):
    """Displays the article details with enhanced styling."""
    # Back button
    if st.button("⬅️ Back to Articles", key="back_button"):
        st.session_state.selected_article_index = None
        st.rerun()
    
    st.divider()
    
    # Title
    title_to_display = article_data.get("original_title", article_data.get("llm_generated_title", "Untitled"))
    st.title(title_to_display)
    
    # Source and date
    date_str = format_date(article_data.get('published_at_dt'))
    source = article_data.get('source', 'Unknown Source')
    st.caption(f"📰 {source} • 📅 {date_str}")
    
    # Featured image
    image_display_url = article_data.get(IMAGE_COLUMN_NAME, None)
    if image_display_url and image_display_url != DEFAULT_IMAGE:
        if isinstance(image_display_url, str) and image_display_url.startswith(('http://', 'https://')):
            st.image(image_display_url, use_container_width=True)
    
    st.divider()
    
    # Article content
    content_to_display = article_data.get(ARTICLE_CONTENT_COLUMN, "Content not available.")
    st.markdown(content_to_display)
    
    st.divider()
    
    # Historical context section
    with st.container():
        st.subheader("📅 Historical Context Timeline")
        with st.expander("View Historical Context", expanded=True):
            historical_context = article_data.get("historical_context", "No historical context available.")
            st.markdown(historical_context)
    
    st.divider()
    
    # Glossary section
    with st.container():
        st.subheader("📘 Glossary of Terms")
        with st.expander("View Glossary", expanded=True):
            glossary = article_data.get("glossary", "No glossary terms available.")
            st.markdown(glossary)

# --- New Function to Search and Sort Articles ---
def filter_and_sort_articles(df, search_query, sort_option):
    """Filters and sorts articles based on search query and sort option."""
    if df is None or df.empty:
        return df
        
    # Filter articles based on search query
    if search_query:
        search_query = search_query.lower()
        mask = (
            df["original_title"].str.lower().str.contains(search_query, na=False) |
            df["llm_generated_title"].str.lower().str.contains(search_query, na=False) |
            df["article_description"].str.lower().str.contains(search_query, na=False) |
            df["source"].str.lower().str.contains(search_query, na=False) |
            df[ARTICLE_CONTENT_COLUMN].str.lower().str.contains(search_query, na=False)
        )
        filtered_df = df[mask].reset_index(drop=True)
    else:
        filtered_df = df.copy()
    
    # Sort articles based on the selected option
    if sort_option == "Newest First":
        if "published_at_dt" in filtered_df.columns and not filtered_df["published_at_dt"].isna().all():
            filtered_df = filtered_df.sort_values(by="published_at_dt", ascending=False).reset_index(drop=True)
    elif sort_option == "Oldest First":
        if "published_at_dt" in filtered_df.columns and not filtered_df["published_at_dt"].isna().all():
            filtered_df = filtered_df.sort_values(by="published_at_dt", ascending=True).reset_index(drop=True)
    elif sort_option == "A-Z":
        title_col = "original_title" if "original_title" in filtered_df.columns else "llm_generated_title"
        filtered_df = filtered_df.sort_values(by=title_col, ascending=True).reset_index(drop=True)
    elif sort_option == "Z-A":
        title_col = "original_title" if "original_title" in filtered_df.columns else "llm_generated_title"
        filtered_df = filtered_df.sort_values(by=title_col, ascending=False).reset_index(drop=True)
    
    return filtered_df

# --- Main Application Logic ---
def main():
    # Setup page
    setup_page_styling()
    
    # Initialize session state
    if 'selected_article_index' not in st.session_state:
        st.session_state.selected_article_index = None
    
    # Load data
    df = load_data(CSV_FILE_PATH)

    # Display appropriate view based on state
    if st.session_state.selected_article_index is None:
        # Homepage View
        st.title("📰 HeadlineTrail")
        st.markdown("Stay informed with the latest news stories, enhanced with historical context and key term definitions.")
        
        # Search and filter options
        col1, col2 = st.columns([7, 3])
        with col1:
            search_query = st.text_input("Search articles...", placeholder="Type keywords...", key="search_box")
        with col2:
            sort_option = st.selectbox("Sort by", ["Newest First", "Oldest First", "A-Z", "Z-A"], key="sort_option")
            
        st.divider()

        if df is not None and not df.empty:
            # Apply search and sort
            filtered_df = filter_and_sort_articles(df, search_query, sort_option)
            
            if not filtered_df.empty:
                num_articles = len(filtered_df)
                num_rows = math.ceil(num_articles / ARTICLES_PER_ROW)
                
                # Display article count
                if search_query:
                    st.write(f"Found {num_articles} articles matching '{search_query}'")
                
                # Display articles in a grid
                for i in range(num_rows):
                    cols = st.columns(ARTICLES_PER_ROW)
                    start_index = i * ARTICLES_PER_ROW
                    end_index = min(start_index + ARTICLES_PER_ROW, num_articles)
                    
                    for j, col in enumerate(cols):
                        article_index = start_index + j
                        if article_index < num_articles:
                            with col:
                                display_article_card(filtered_df.iloc[article_index], article_index)
            else:
                if search_query:
                    st.warning(f"No articles found matching '{search_query}'")
                else:
                    st.warning("No articles found in the database.")
                    st.info("The CSV file appears to be empty. Please add articles to your dataset.")
                
        elif df is not None and df.empty:
            st.warning("No articles found in the database.")
            st.info("The CSV file appears to be empty. Please add articles to your dataset.")

    else:  # Article Detail View
        if df is not None and not df.empty:
            selected_index = st.session_state.selected_article_index
            if 0 <= selected_index < len(df):
                selected_article_data = df.iloc[selected_index]
                display_article_detail(selected_article_data)
            else:
                st.error("Invalid article selection. Returning home.")
                st.session_state.selected_article_index = None
                if st.button("Return Home"): st.rerun()
        else:
            st.error("Data could not be loaded. Returning home.")
            st.session_state.selected_article_index = None
            if st.button("Return Home"): st.rerun()

if __name__ == "__main__":
    main()
