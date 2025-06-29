document.addEventListener('DOMContentLoaded', () => {
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
    const detailBackButton = document.getElementById('back-button');
    const detailTitle = document.getElementById('detail-title');
    const detailCaption = document.getElementById('detail-caption');
    const detailImage = document.getElementById('detail-image');
    const detailContent = document.getElementById('detail-content');
    const detailTimeline = document.getElementById('detail-timeline');
    const detailGlossary = document.getElementById('detail-glossary');
    const detailLinkContainer = document.getElementById('detail-link-container');

    const backendBaseUrl = 'https://headlinetrail.onrender.com';
    const articlesUrl = `${backendBaseUrl}/articles`;
    const filterOptionsUrl = `${backendBaseUrl}/filter-options`;

    let currentFilters = { search: '', sort_option: 'Newest First', category: 'All Categories', month: 'All Months' };
    let availableFilterOptions = { categories: ["All Categories"], months: ["All Months"] };
    
    const IMAGE_COLUMN_NAME = "article_url_to_image";
    const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80";

    function displayMessage(element, message, isError = false) {
        element.textContent = message;
        element.style.display = 'block';
        if(isError) { element.style.backgroundColor = '#f8d7da'; element.style.color = '#842029'; }
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

    async function fetchFilterOptions() {
        try {
            const response = await fetch(filterOptionsUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const optionsData = await response.json();
            availableFilterOptions = {
                categories: optionsData.categories || ["All Categories"],
                months: optionsData.months || ["All Months"],
            };
            populateFilterOptions();
        } catch (error) {
            displayMessage(errorMessageDiv, `Could not load filter options: ${error.message}.`, true);
        }
    }

    function populateFilterOptions() {
        const populateSelect = (selectEl, options) => {
            selectEl.innerHTML = '';
            options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt; option.textContent = opt;
                selectEl.appendChild(option);
            });
        };
        populateSelect(categorySelect, availableFilterOptions.categories);
        populateSelect(monthSelect, availableFilterOptions.months);
    }

    async function fetchAndRenderArticles(filters) {
        hideMessages();
        loadingIndicator.style.display = 'block';
        newsGrid.innerHTML = '';
        const params = new URLSearchParams();
        if (filters.search) params.append('search', filters.search);
        if (filters.sort_option) params.append('sort', filters.sort_option);
        if (filters.month && filters.month !== 'All Months') params.append('month', filters.month);
        if (filters.category && filters.category !== "All Categories") params.append('category', filters.category);
        
        try {
            const response = await fetch(`${articlesUrl}?${params.toString()}`);
            loadingIndicator.style.display = 'none';
            if (!response.ok) throw new Error(`Network error (${response.status})`);
            const articles = await response.json();
            renderArticleGrid(articles);
        } catch (error) {
            displayMessage(errorMessageDiv, `Failed to load articles: ${error.message}. Ensure backend is running.`, true);
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
                <img src="${imageUrl}" alt="" onerror="this.onerror=null;this.src='${DEFAULT_IMAGE}';">
                <div class="card-content">
                    <h6></h6>
                    <div class="caption"></div>
                    <button>Read Article</button>
                </div>
            `;
            card.querySelector('h6').textContent = article.original_title || 'Untitled';
            card.querySelector('.caption').textContent = `${article.source || 'Unknown'} | ${article.published_at_formatted || 'Unknown Date'}`;
            card.querySelector('button').addEventListener('click', () => showArticleDetail(article));
            newsGrid.appendChild(card);
        });
    }

    function showArticleDetail(article) {
        detailTitle.textContent = article.original_title || 'Untitled';
        detailCaption.textContent = `Source: ${article.source || 'Unknown'} | Published: ${article.published_at_formatted || 'Unknown'}`;
        detailImage.src = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
        detailImage.style.display = 'block';
        detailContent.textContent = article.article_content || 'Content not available.';

        detailLinkContainer.innerHTML = ''; 
        if (article.original_url && article.original_url !== '#') {
            const linkButton = document.createElement('a');
            linkButton.href = article.original_url;
            linkButton.textContent = "Read Article Online";
            linkButton.target = "_blank";
            linkButton.rel = "noopener noreferrer";
            linkButton.className = "read-more-button";
            detailLinkContainer.appendChild(linkButton);
        }

        const renderList = (element, data, template) => {
            element.innerHTML = '';
            if (data && data.length > 0) {
                data.forEach(entry => {
                    const entryDiv = document.createElement('div');
                    entryDiv.innerHTML = template(entry);
                    element.appendChild(entryDiv);
                });
            } else {
                element.innerHTML = `<p>No ${element.id.includes('timeline') ? 'timeline entries' : 'glossary terms'} available.</p>`;
            }
        };
        renderList(detailTimeline, article.historical_context, e => `<p><strong>${e.year||'?'}: ${e.title||'Event'}</strong></p><p style="margin-top: 0.2em;">${e.summary||''}</p>`);
        renderList(detailGlossary, article.glossary, e => `<strong>${e.word||'?'}:</strong> ${e.definition||''}`);
        
        switchView('article-detail');
    }

    function handleFilterChange() {
        currentFilters = { search: searchInput.value, sort_option: sortSelect.value, category: categorySelect.value, month: monthSelect.value };
        fetchAndRenderArticles(currentFilters);
    }
    
    [searchInput, sortSelect, categorySelect, monthSelect].forEach(el => {
        el.addEventListener('change', handleFilterChange);
    });
    searchInput.addEventListener('input', handleFilterChange);

    detailBackButton.addEventListener('click', () => switchView('news-grid'));

    function init() {
        switchView('news-grid');
        loadingIndicator.style.display = 'block';
        fetchFilterOptions().then(() => {
            fetchAndRenderArticles(currentFilters);
        });
    }
    init();
});
