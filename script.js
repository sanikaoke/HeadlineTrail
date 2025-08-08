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

    let currentFilters = {
        search: '',
        sort_option: 'Newest First',
        category: 'All Categories',
        month: 'All Months'
    };

    const IMAGE_COLUMN_NAME = "article_url_to_image";
    const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1516116216624-53e697fedbe0?auto=format&fit=crop&w=600&q=80";

    function switchView(view) {
        newsGrid.style.display = view === 'news-grid' ? 'grid' : 'none';
        articleDetailView.style.display = view === 'detail' ? 'block' : 'none';
        filterControlsDiv.style.display = view === 'news-grid' ? 'flex' : 'none';
    }

    function renderTimeline(items) {
        detailTimeline.innerHTML = '';
        if (items?.length > 0) {
            items.forEach(e => {
                const entryDiv = document.createElement('div');
                entryDiv.innerHTML = `
                    <strong>${e.year || ''} – ${e.title || ''}</strong>
                    <p>${e.summary || ''}</p>
                `;
                detailTimeline.appendChild(entryDiv);
            });
        } else {
            detailTimeline.innerHTML = `<p>No timeline entries available.</p>`;
        }
    }

    function renderGlossary(items) {
        detailGlossary.innerHTML = '';
        if (items?.length > 0) {
            items.forEach(e => {
                const entryDiv = document.createElement('div');
                entryDiv.innerHTML = `<strong>${e.word || '?'}:</strong> ${e.definition || ''}`;
                detailGlossary.appendChild(entryDiv);
            });
        } else {
            detailGlossary.innerHTML = `<p>No glossary terms available.</p>`;
        }
    }

    function renderQuickSummary(article) {
        detailContent.innerHTML = '';
        if (article.summarized_content?.trim()) {
            const bulletPoints = article.summarized_content
                .split('- ')
                .filter(point => point.trim() !== '');
            const summaryHTML = `
                <h3>Article Summary</h3>
                <ul>${bulletPoints.map(p => `<li>${p.trim()}</li>`).join('')}</ul>
            `;
            detailContent.insertAdjacentHTML('beforeend', summaryHTML);
        } else {
            detailContent.innerHTML = `<p>No summary available.</p>`;
        }
    }

    function showArticleDetail(article) {
        detailTitle.textContent = article.original_title || 'Untitled';
        detailCaption.innerHTML = [
            `By ${article.author || 'Unknown author'}`,
            `Source: ${article.source || 'Unknown'}`,
            `Published: ${article.published_at_formatted || 'Unknown'}`
        ].join(' | ');
        detailImage.src = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
        detailImage.style.display = 'block';
        detailImage.onerror = () => { detailImage.src = DEFAULT_IMAGE; };

        detailLinkContainer.innerHTML = '';
        if (article.original_url) {
            const a = document.createElement('a');
            a.href = article.original_url;
            a.textContent = 'Read Article Online';
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            detailLinkContainer.appendChild(a);
        }

        // New Quick Summary
        renderQuickSummary(article);

        // Timeline under summary
        renderTimeline(article.historical_context || []);

        // Glossary in sidebar
        renderGlossary(article.glossary || []);

        /* OLD summary rendering kept for reference:
        if (article.summarized_content && article.summarized_content.trim() !== "") {
            const bulletPoints = article.summarized_content
                .split('- ')
                .filter(point => point.trim() !== '');
            const summaryHTML = `
                <h3 style="margin-top:1em;">Article Summary</h3>
                <ul style="padding-left:1.2em;">
                    ${bulletPoints.map(point => `<li>${point.trim()}</li>`).join('')}
                </ul>
            `;
            detailContent.insertAdjacentHTML('afterend', summaryHTML);
        }
        */

        switchView('detail');
    }

    async function fetchAndRenderArticles(filters) {
        loadingIndicator.style.display = 'block';
        newsGrid.innerHTML = '';
        const params = new URLSearchParams();
        if (filters.search) params.append('search', filters.search);
        if (filters.sort_option) params.append('sort', filters.sort_option);
        if (filters.category && filters.category !== 'All Categories') {
            params.append('category', filters.category);
        }
        try {
            const resp = await fetch(`${articlesUrl}?${params.toString()}`);
            loadingIndicator.style.display = 'none';
            const articles = await resp.json();
            articles.forEach(article => {
                const card = document.createElement('div');
                card.className = 'news-card';
                const imageUrl = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
                card.innerHTML = `
                    <img src="${imageUrl}" alt="">
                    <div class="card-content">
                        <h6>${article.original_title || 'Untitled'}</h6>
                        <div class="caption">By ${article.author || 'Unknown author'} | Published: ${article.published_at_formatted || 'Unknown'}</div>
                        <button>Read Article</button>
                    </div>
                `;
                card.querySelector('button').addEventListener('click', () => showArticleDetail(article));
                newsGrid.appendChild(card);
            });
        } catch (err) {
            console.error(err);
        }
    }

    sortSelect.addEventListener('change', () => fetchAndRenderArticles(currentFilters));
    categorySelect.addEventListener('change', () => fetchAndRenderArticles(currentFilters));
    searchInput.addEventListener('input', () => fetchAndRenderArticles(currentFilters));
    detailBackButton.addEventListener('click', () => switchView('news-grid'));

    (function init() {
        fetchAndRenderArticles(currentFilters);
    })();
});
