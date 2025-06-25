document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const newsGrid = document.getElementById('news-grid');
    const articleDetailView = document.getElementById('article-detail');
    const filterControlsDiv = document.getElementById('filter-controls');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessageDiv = document.getElementById('error-message');
    const noResultsMessageDiv = document.getElementById('no-results-message');
    const searchInput = document.getElementById('search-input');
    const sortSelect = document.getElementById('sort-select');
    const categorySelect = document.getElementById('category-select'); // Single select
    const monthSelect = document.getElementById('month-select');
    const daySelect = document.getElementById('day-select');
    const refreshButton = document.getElementById('refresh-button');
    const detailBackButton = document.getElementById('back-button');
    const detailTitle = document.getElementById('detail-title');
    const detailCaption = document.getElementById('detail-caption');
    const detailImage = document.getElementById('detail-image');
    const detailContent = document.getElementById('detail-content');
    const detailTimeline = document.getElementById('detail-timeline');
    const detailGlossary = document.getElementById('detail-glossary');
    const detailLinkContainer = document.getElementById('detail-link-container');

    // --- API URLs ---
    const backendBaseUrl = '';
    const articlesUrl = '${backendBaseUrl}/api/articles';
    const filterOptionsUrl = '${backendBaseUrl}/api/filter-options';

    // --- State ---
    let currentFilters = {
        search: '', sort_option: 'Newest First',
        category: 'All Categories', // Single category state
        month: 'All Months', day: 'All Days'
    };
    let availableFilterOptions = {
        categories: ["All Categories"], months: ["All Months"],
        days_by_month: {"All Months": ["All Days"]},
        all_unique_days: ["All Days"]
    };
    // --- Constants ---
    const IMAGE_COLUMN_NAME = "article_url_to_image";
    const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80";


    // --- Utility Functions ---
    function displayMessage(element, message, isError = false) {
        element.textContent = message; element.style.display = 'block';
        element.style.color = isError ? '#842029' : '#6c757d';
        element.style.backgroundColor = isError ? '#f8d7da' : '#e9ecef';
        element.style.border = `1px solid ${isError ? '#f5c2c7' : '#ced4da'}`;
        if (element === errorMessageDiv || element === noResultsMessageDiv) {
            if (newsGrid) newsGrid.style.display = 'none';
            if (articleDetailView) articleDetailView.style.display = 'none';
        }
    }
    function hideMessages() {
        loadingIndicator.style.display = 'none'; errorMessageDiv.style.display = 'none';
        noResultsMessageDiv.style.display = 'none';
    }

    // --- UPDATED switchView function ---
    function switchView(viewIdToShow) {
        console.log(`Switching view to: ${viewIdToShow}`);
        const gridView = document.getElementById('news-grid');
        const detailView = document.getElementById('article-detail');
        const filters = document.getElementById('filter-controls'); // Target filters

        // Hide all view containers first
        document.querySelectorAll('.view').forEach(view => { if (view) view.style.display = 'none'; });

        // Show target view and control filter visibility
        if (viewIdToShow === 'news-grid') {
             if (gridView) gridView.style.display = 'grid';
             if (filters) filters.style.display = 'flex'; // Show filters
             if (gridView) gridView.classList.add('active-view');
             if (detailView) detailView.classList.remove('active-view');
        } else if (viewIdToShow === 'article-detail') {
             if (detailView) detailView.style.display = 'block';
             if (filters) filters.style.display = 'none'; // Hide filters
             if (detailView) detailView.classList.add('active-view');
             if (gridView) gridView.classList.remove('active-view');
        } else { /* Default */ if (gridView) gridView.style.display = 'grid'; if (filters) filters.style.display = 'flex'; }
        window.scrollTo(0, 0);
    }

    // --- Data Fetching and Rendering ---
    async function fetchFilterOptions() {
        console.log("Fetching filter options...");
        try {
            const response = await fetch(filterOptionsUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const optionsData = await response.json();
            // Validate structure slightly
            availableFilterOptions = {
                categories: optionsData.categories || ["All Categories"],
                months: optionsData.months || ["All Months"],
                days_by_month: optionsData.days_by_month || {"All Months": ["All Days"]},
                all_unique_days: optionsData.all_unique_days || ["All Days"] // Store all unique days
            };
            console.log("Filter options fetched:", availableFilterOptions);
            populateFilterOptions();
        } catch (error) {
            console.error("Could not fetch filter options:", error);
            displayMessage(errorMessageDiv, `Could not load filter options: ${error.message}. Backend down?`, true);
        }
    }

    function populateFilterOptions() {
        // Categories - Single select
        categorySelect.innerHTML = '';
        availableFilterOptions.categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat; option.textContent = cat;
            categorySelect.appendChild(option);
        });
        categorySelect.value = currentFilters.category; // Set current

        // Months
        monthSelect.innerHTML = '';
        availableFilterOptions.months.forEach(month => {
            const option = document.createElement('option');
            option.value = month; option.textContent = month;
            monthSelect.appendChild(option);
        });
        monthSelect.value = currentFilters.month;

        populateDayOptions(); // Populate days
    }

    function populateDayOptions() {
        const selectedMonth = monthSelect.value;
        let daysToShow = ["All Days"]; // Default

        if (selectedMonth === "All Months") {
            // If All Months, show all unique days found across dataset
            daysToShow = availableFilterOptions.all_unique_days || ["All Days"];
        } else {
            // Otherwise, show days specific to the selected month
            daysToShow = availableFilterOptions.days_by_month[selectedMonth] || ["All Days"];
        }

        const currentDayValue = daySelect.value; // Store current value before clearing
        daySelect.innerHTML = ''; // Clear existing options
        daysToShow.forEach(day => {
            const option = document.createElement('option');
            option.value = day;
            option.textContent = day; // Display the value ("All Days" or "5" or "15")
            daySelect.appendChild(option);
        });

        // Set value, default to "All Days" if current selection invalid for the *new* options
        daySelect.value = daysToShow.includes(currentDayValue) ? currentDayValue : "All Days";

        // Update state if reset happened implicitly
        if (!daysToShow.includes(currentFilters.day)) {
             currentFilters.day = "All Days";
        }
        console.log(`Populated days for selection '${selectedMonth}':`, daysToShow);
    }

    async function fetchAndRenderArticles(filters) {
        hideMessages();
        loadingIndicator.style.display = 'block';
        newsGrid.innerHTML = ''; // Clear grid

        const params = new URLSearchParams();
        if (filters.search) params.append('search', filters.search);
        if (filters.sort_option) params.append('sort', filters.sort_option);
        if (filters.month && filters.month !== 'All Months') params.append('month', filters.month);
         // Only send day if it's NOT "All Days"
        if (filters.day && filters.day !== 'All Days') params.append('day', filters.day);// Send single category value
        if (filters.category && filters.category !== "All Categories") {
             params.append('category', filters.category);
        }

        const urlWithParams = `${articlesUrl}?${params.toString()}`;
        console.log(`Fetching articles from: ${urlWithParams}`);

        try {
            const response = await fetch(urlWithParams);
            loadingIndicator.style.display = 'none';
            if (!response.ok) {
                 const errData = await response.json().catch(() => ({ error: 'Unknown server error' }));
                 throw new Error(`Network error (${response.status}). Server: ${errData.error || 'N/A'}`);
            }
            const articles = await response.json();
            console.log(`Fetched ${articles.length} articles.`);
            renderArticleGrid(articles);
            // Ensure grid is shown (caller might switch later)
            // switchView('news-grid'); // Let initial load handle the first switch
        } catch (error) {
            console.error('Error fetching/rendering articles:', error);
            displayMessage(errorMessageDiv, `Failed to load articles: ${error.message}. Ensure backend is running.`, true);
            switchView('news-grid'); // Show grid area for error
        }
    }

    function renderArticleGrid(articles) {
        newsGrid.innerHTML = ''; // Clear previous grid

        if (!articles || articles.length === 0) {
            displayMessage(noResultsMessageDiv, "No articles found matching your filters.");
            newsGrid.style.display = 'block';
            return;
        } else {
             noResultsMessageDiv.style.display = 'none';
             newsGrid.style.display = 'grid'; // Set display back to grid
        }

        articles.forEach((article) => { // No need for index here
            const card = document.createElement('div');
            card.className = 'news-card';

            const imgContainer = document.createElement('div');
            const img = document.createElement('img');
            let imageUrl = article[IMAGE_COLUMN_NAME];
            if (!imageUrl || typeof imageUrl !== 'string' || !(imageUrl.startsWith('http') || imageUrl.startsWith('data:'))) imageUrl = DEFAULT_IMAGE;
            img.src = imageUrl; img.alt = article.original_title || 'News';
            img.onerror = () => { img.src = DEFAULT_IMAGE; img.alt = 'Default';};
            imgContainer.appendChild(img);
            card.appendChild(imgContainer);

            const contentContainer = document.createElement('div');
            contentContainer.className = 'card-content';

            const title = document.createElement('h6');
            let displayTitle = article.original_title || 'Untitled';
            title.textContent = displayTitle //.length > 70 ? displayTitle.substring(0, 70) + '...' : displayTitle;
            contentContainer.appendChild(title);

            const caption = document.createElement('div');
            caption.className = 'caption';
            const source = article.source || 'Unknown';
            const dateStr = article.published_at_formatted || 'Unknown Date';
            caption.textContent = `${source} | ${dateStr}`;
            contentContainer.appendChild(caption);

            const button = document.createElement('button');
            button.textContent = 'Read Article';
            button.onclick = () => showArticleDetail(article); // Pass the full article object
            contentContainer.appendChild(button);

            card.appendChild(contentContainer);
            newsGrid.appendChild(card);
        });
    }

    function showArticleDetail(article) {
        console.log("Showing detail for:", article.original_title);

        detailTitle.textContent = article.original_title || 'Untitled';
        detailCaption.textContent = `Source: ${article.source || 'Unknown'} | Published: ${article.published_at_formatted || 'Unknown'}`;

        let imageUrl = article[IMAGE_COLUMN_NAME];
        if (imageUrl && imageUrl !== DEFAULT_IMAGE && typeof imageUrl === 'string' && (imageUrl.startsWith('http') || imageUrl.startsWith('data:'))) {
            detailImage.src = imageUrl; detailImage.alt = article.original_title; detailImage.style.display = 'block';
        } else { detailImage.style.display = 'none'; }

        detailLinkContainer.innerHTML = '';
        if (article.article_url && article.article_url !== '#') {
             const linkButton = document.createElement('a');
             linkButton.href = article.article_url; linkButton.textContent = "Read Original Article Online";
             linkButton.target = "_blank"; linkButton.rel = "noopener noreferrer";
             linkButton.className = "detail-link-button";
             detailLinkContainer.appendChild(linkButton);
        }

        // Handle article content and read more button
        const detailContent = document.getElementById('detail-content');
        const readMoreContainer = document.getElementById('read-more-container');
        
        // Clear previous content and button
        detailContent.textContent = article.article_content || 'Content not available';
        readMoreContainer.innerHTML = '';

        // Always show the read more button if we have a valid URL
        if (article.article_url && article.article_url !== '#') {
            const readMoreLink = document.createElement('a');
            readMoreLink.href = article.article_url;
            readMoreLink.className = 'read-more-button';
            readMoreLink.innerHTML = '📰 Read full article online';
            readMoreLink.target = '_blank';
            readMoreLink.rel = 'noopener noreferrer';
            
            readMoreContainer.appendChild(readMoreLink);
            readMoreContainer.style.display = 'block';
        } else {
            readMoreContainer.style.display = 'none';
        }

        // Timeline
        detailTimeline.innerHTML = '';
        const timelineData = article.historical_context || []; // Already parsed by backend
        if (Array.isArray(timelineData) && timelineData.length > 0) {
             timelineData.forEach(entry => {
                const entryDiv = document.createElement('div');
                const header = document.createElement('p');
                header.innerHTML = `<strong>${entry.year || '?'}: ${entry.title || 'Event'}</strong>`;
                const summary = document.createElement('p');
                summary.textContent = entry.summary || '';
                summary.style.marginTop = '0.2em';
                entryDiv.appendChild(header);
                if (summary.textContent) entryDiv.appendChild(summary);
                detailTimeline.appendChild(entryDiv);
             });
        } else { detailTimeline.innerHTML = '<p>No timeline entries available.</p>'; }

         // Glossary
        detailGlossary.innerHTML = '';
        const glossaryData = article.glossary || []; // Already parsed by backend
        if (Array.isArray(glossaryData) && glossaryData.length > 0) {
            glossaryData.forEach(entry => {
                const entryDiv = document.createElement('div');
                const term = document.createElement('strong');
                term.textContent = `${entry.word || '?'}: `;
                const definition = document.createTextNode(entry.definition || '');
                entryDiv.appendChild(term); entryDiv.appendChild(definition);
                detailGlossary.appendChild(entryDiv);
            });
        } else { detailGlossary.innerHTML = '<p>No glossary terms available.</p>'; }

        switchView('article-detail'); // Activate the detail view
    }


    // --- Event Listeners ---
    function handleFilterChange() {
        // Read current values from DOM into state
        currentFilters.search = searchInput.value;
        currentFilters.sort_option = sortSelect.value;
        currentFilters.category = categorySelect.value; // Read single category
        currentFilters.month = monthSelect.value;
        currentFilters.day = daySelect.value; // Day is already updated by month listener if needed

        console.log("Filters changed, new state:", currentFilters);
        fetchAndRenderArticles(currentFilters); // Refetch based on new filters
        // Don't switch view here, stay on grid
    }

    // Add listeners that call the handler
    searchInput.addEventListener('input', handleFilterChange);
    sortSelect.addEventListener('change', handleFilterChange);
    categorySelect.addEventListener('change', handleFilterChange);
    monthSelect.addEventListener('change', () => {
        // Update day options first, then trigger general filter change handler
        populateDayOptions(); // Update day options based on new month selection
        // Ensure the day state reflects the reset BEFORE fetching
        currentFilters.day = daySelect.value; // Use the updated day value
        handleFilterChange(); // Fetch with updated month and reset day
    });
    daySelect.addEventListener('change', handleFilterChange);

    // Detail View Back Button
    detailBackButton.addEventListener('click', () => {
        switchView('news-grid'); // Show grid and filters
    });

     // Refresh Button
     refreshButton.addEventListener('click', () => {
         console.log("Refresh button clicked.");
         displayMessage(loadingIndicator, '🔄 Refreshing data...', false);
         newsGrid.innerHTML = '';
         fetchFilterOptions().then(() => { // Re-fetch options
             // Fetch articles with current filter state
             fetchAndRenderArticles(currentFilters);
             switchView('news-grid'); // Ensure grid shown
         });
     });

    // --- Initial Load ---
    console.log("Initial page load: Fetching options and articles...");
    displayMessage(loadingIndicator, '🔄 Loading initial data...', false);
    switchView('news-grid'); // Ensure grid is default view initially
    fetchFilterOptions().then(() => {
        fetchAndRenderArticles(currentFilters); // Fetch articles
    });

    async function handleRefresh() {
        const refreshButton = document.getElementById('refresh-button');
        const loadingIndicator = document.getElementById('loading-indicator');
        
        try {
            refreshButton.disabled = true;
            refreshButton.textContent = '🔄 Fetching Latest News...';
            loadingIndicator.style.display = 'block';

            const response = await fetch('http://127.0.0.1:5001/api/fetch-latest-news', {
                method: 'POST',
            });

            const result = await response.json();
            
            if (result.success) {
                await fetchFilterOptions();
                await fetchAndRenderArticles(currentFilters);
                
                // Show detailed success message
                const message = `Successfully fetched ${result.new_articles_count} new articles\n` +
                              `Dates processed: ${result.details.dates_processed.length}`;
                showNotification(message);
            } else {
                throw new Error(result.message || 'Failed to process news articles');
            }
            
        } catch (error) {
            console.error('Error fetching latest news:', error);
            showNotification('Failed to fetch latest news: ' + error.message, 'error');
        } finally {
            refreshButton.disabled = false;
            refreshButton.textContent = '🔄 Fetch Latest News';
            loadingIndicator.style.display = 'none';
        }
    }

    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
    
        // Remove notification after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    // Add event listener for refresh button
    refreshButton.removeEventListener('click', handleFilterChange);  // Remove old listener if exists
    refreshButton.addEventListener('click', handleRefresh);

}); // End DOMContentLoaded
