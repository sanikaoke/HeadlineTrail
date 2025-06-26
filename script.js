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
    const categorySelect = document.getElementById('category-select');
    const monthSelect = document.getElementById('month-select');
    const daySelect = document.getElementById('day-select');
    const detailBackButton = document.getElementById('back-button');
    const detailTitle = document.getElementById('detail-title');
    const detailCaption = document.getElementById('detail-caption');
    const detailImage = document.getElementById('detail-image');
    const detailContent = document.getElementById('detail-content');
    const detailTimeline = document.getElementById('detail-timeline');
    const detailGlossary = document.getElementById('detail-glossary');
    const detailLinkContainer = document.getElementById('detail-link-container');
    const readMoreContainer = document.getElementById('read-more-container');

    // --- API URLs ---
    // This now points to your backend hosted on Render.
    const backendBaseUrl = 'https://headlinetrail-backend.onrender.com'; // Replace with your actual Render URL if it's different
    const articlesUrl = `${backendBaseUrl}/articles`;
    const filterOptionsUrl = `${backendBaseUrl}/filter-options`;

    // --- State ---
    let currentFilters = {
        search: '',
        sort_option: 'Newest First',
        category: 'All Categories',
        month: 'All Months',
        day: 'All Days'
    };
    let availableFilterOptions = {
        categories: ["All Categories"],
        months: ["All Months"],
        days_by_month: { "All Months": ["All Days"] },
        all_unique_days: ["All Days"]
    };
    
    // --- Constants ---
    const IMAGE_COLUMN_NAME = "article_url_to_image";
    const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80";

    // --- Utility Functions ---
    function displayMessage(element, message, isError = false) {
        element.textContent = message;
        element.style.display = 'block';
        if (element === errorMessageDiv || element === noResultsMessageDiv) {
            if (newsGrid) newsGrid.style.display = 'none';
        }
    }

    function hideMessages() {
        loadingIndicator.style.display = 'none';
        errorMessageDiv.style.display = 'none';
        noResultsMessageDiv.style.display = 'none';
    }

    function switchView(viewIdToShow) {
        document.querySelectorAll('.view').forEach(view => { if (view) view.style.display = 'none'; });
        const viewToShow = document.getElementById(viewIdToShow);
        if (viewToShow) {
            viewToShow.style.display = (viewIdToShow === 'news-grid') ? 'grid' : 'block';
        }
        filterControlsDiv.style.display = (viewIdToShow === 'news-grid') ? 'flex' : 'none';
        window.scrollTo(0, 0);
    }

    // --- Data Fetching and Rendering ---
    async function fetchFilterOptions() {
        try {
            const response = await fetch(filterOptionsUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const optionsData = await response.json();
            availableFilterOptions = {
                categories: optionsData.categories || ["All Categories"],
                months: optionsData.months || ["All Months"],
                days_by_month: optionsData.days_by_month || { "All Months": ["All Days"] },
                all_unique_days: optionsData.all_unique_days || ["All Days"]
            };
            populateFilterOptions();
        } catch (error) {
            console.error("Could not fetch filter options:", error);
            displayMessage(errorMessageDiv, `Could not load filter options: ${error.message}.`, true);
        }
    }

    function populateFilterOptions() {
        categorySelect.innerHTML = '';
        availableFilterOptions.categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            categorySelect.appendChild(option);
        });
        monthSelect.innerHTML = '';
        availableFilterOptions.months.forEach(month => {
            const option = document.createElement('option');
            option.value = month;
            option.textContent = month;
            monthSelect.appendChild(option);
        });
        populateDayOptions();
    }

    function populateDayOptions() {
        const selectedMonth = monthSelect.value;
        let daysToShow = (selectedMonth === "All Months") ? availableFilterOptions.all_unique_days : availableFilterOptions.days_by_month[selectedMonth];
        if (!daysToShow) daysToShow = ["All Days"];
        
        const currentDayValue = daySelect.value;
        daySelect.innerHTML = '';
        daysToShow.forEach(day => {
            const option = document.createElement('option');
            option.value = day;
            option.textContent = day;
            daySelect.appendChild(option);
        });
        daySelect.value = daysToShow.includes(currentDayValue) ? currentDayValue : "All Days";
    }

    async function fetchAndRenderArticles(filters) {
        hideMessages();
        loadingIndicator.style.display = 'block';
        newsGrid.innerHTML = '';

        const params = new URLSearchParams();
        if (filters.search) params.append('search', filters.search);
        if (filters.sort_option) params.append('sort', filters.sort_option);
        if (filters.month && filters.month !== 'All Months') params.append('month', filters.month);
        if (filters.day && filters.day !== 'All Days') params.append('day', filters.day);
        if (filters.category && filters.category !== "All Categories") params.append('category', filters.category);

        const urlWithParams = `${articlesUrl}?${params.toString()}`;

        try {
            const response = await fetch(urlWithParams);
            loadingIndicator.style.display = 'none';
            if (!response.ok) {
                throw new Error(`Network error (${response.status}). Server may be starting up or down.`);
            }
            const articles = await response.json();
            renderArticleGrid(articles);
        } catch (error) {
            console.error('Error fetching/rendering articles:', error);
            displayMessage(errorMessageDiv, `Failed to load articles: ${error.message}`, true);
        }
    }

    function renderArticleGrid(articles) {
        newsGrid.innerHTML = '';
        if (!articles || articles.length === 0) {
            displayMessage(noResultsMessageDiv, "No articles found matching your filters.");
            return;
        }
        newsGrid.style.display = 'grid';
        articles.forEach(article => {
            const card = document.createElement('div');
            card.className = 'news-card';
            let imageUrl = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
            card.innerHTML = `
                <img src="${imageUrl}" alt="${article.original_title || 'News'}" onerror="this.onerror=null;this.src='${DEFAULT_IMAGE}';">
                <div class="card-content">
                    <h6>${article.original_title || 'Untitled'}</h6>
                    <div class="caption">${article.source || 'Unknown'} | ${article.published_at_formatted || 'Unknown Date'}</div>
                    <button>Read Article</button>
                </div>
            `;
            card.querySelector('button').addEventListener('click', () => showArticleDetail(article));
            newsGrid.appendChild(card);
        });
    }

    function showArticleDetail(article) {
        detailTitle.textContent = article.original_title || 'Untitled';
        detailCaption.textContent = `Source: ${article.source || 'Unknown'} | Published: ${article.published_at_formatted || 'Unknown'}`;
        
        let imageUrl = article[IMAGE_COLUMN_NAME];
        if (imageUrl) {
            detailImage.src = imageUrl;
            detailImage.style.display = 'block';
        } else {
            detailImage.style.display = 'none';
        }

        detailContent.textContent = article.article_content || 'Content not available.';

        // This is the corrected code for the "Read Full Article" button
        readMoreContainer.innerHTML = '';
        if (article.original_url && article.original_url !== '#') {
            const readMoreLink = document.createElement('a');
            readMoreLink.href = article.original_url;
            readMoreLink.className = 'read-more-button';
            readMoreLink.innerHTML = '📰 Read full article online';
            readMoreLink.target = '_blank';
            readMoreLink.rel = 'noopener noreferrer';
            readMoreContainer.appendChild(readMoreLink);
        }

        detailTimeline.innerHTML = '';
        const timelineData = article.historical_context || [];
        if (timelineData.length > 0) {
            timelineData.forEach(entry => {
                const entryDiv = document.createElement('div');
                entryDiv.innerHTML = `<p><strong>${entry.year || '?'}: ${entry.title || 'Event'}</strong></p><p>${entry.summary || ''}</p>`;
                detailTimeline.appendChild(entryDiv);
            });
        } else {
            detailTimeline.innerHTML = '<p>No timeline entries available.</p>';
        }

        detailGlossary.innerHTML = '';
        const glossaryData = article.glossary || [];
        if (glossaryData.length > 0) {
            glossaryData.forEach(entry => {
                const entryDiv = document.createElement('div');
                entryDiv.innerHTML = `<strong>${entry.word || '?'}:</strong> ${entry.definition || ''}`;
                detailGlossary.appendChild(entryDiv);
            });
        } else {
            detailGlossary.innerHTML = '<p>No glossary terms available.</p>';
        }

        switchView('article-detail');
    }

    // --- Event Listeners ---
    function handleFilterChange() {
        currentFilters.search = searchInput.value;
        currentFilters.sort_option = sortSelect.value;
        currentFilters.category = categorySelect.value;
        currentFilters.month = monthSelect.value;
        currentFilters.day = daySelect.value;
        fetchAndRenderArticles(currentFilters);
    }

    searchInput.addEventListener('input', handleFilterChange);
    sortSelect.addEventListener('change', handleFilterChange);
    categorySelect.addEventListener('change', handleFilterChange);
    daySelect.addEventListener('change', handleFilterChange);
    monthSelect.addEventListener('change', () => {
        populateDayOptions();
        handleFilterChange();
    });

    detailBackButton.addEventListener('click', () => switchView('news-grid'));

    // --- Initial Load ---
    function init() {
        hideMessages();
        loadingIndicator.style.display = 'block';
        fetchFilterOptions().then(() => {
            fetchAndRenderArticles(currentFilters);
        });
    }

    init();
});
