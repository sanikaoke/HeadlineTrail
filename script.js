document.addEventListener('DOMContentLoaded', () => {
    const newsGrid              = document.getElementById('news-grid');
    const articleDetailView     = document.getElementById('article-detail');
    const filterControlsDiv     = document.getElementById('filter-controls');
    const loadingIndicator      = document.getElementById('loading-indicator');
    const errorMessageDiv       = document.getElementById('error-message');
    const noResultsMessageDiv   = document.getElementById('no-results-message');
    const searchInput           = document.getElementById('search-input');
    const sortSelect            = document.getElementById('sort-select');
    const categorySelect        = document.getElementById('category-select');
    const monthSelect           = document.getElementById('month-select');
    const detailBackButton      = document.getElementById('back-button');
    const detailTitle           = document.getElementById('detail-title');
    const detailCaption         = document.getElementById('detail-caption');
    const detailImage           = document.getElementById('detail-image');
    const detailContent         = document.getElementById('detail-content');
    const detailTimeline        = document.getElementById('detail-timeline');
    const detailGlossary        = document.getElementById('detail-glossary');
    const detailLinkContainer   = document.getElementById('detail-link-container');

    const backendBaseUrl     = 'https://headlinetrail.onrender.com';
    const articlesUrl        = `${backendBaseUrl}/articles`;
    const filterOptionsUrl   = `${backendBaseUrl}/filter-options`;

    // initial filter state
    let currentFilters = {
        search:      '',
        sort_option: 'Newest First',
        category:    'All Categories',
        month:       'All Months'
    };

    // will be populated by the API
    let availableFilterOptions = {
        categories: ["All Categories"],
        months:     ["All Months"]
    };

    const IMAGE_COLUMN_NAME = "article_url_to_image";
    const DEFAULT_IMAGE     = "https://images.unsplash.com/photo-1516116216624-53e697fedbe0?auto=format&fit=crop&w=600&q=80";

    function displayMessage(el, msg, isError = false) {
        el.textContent = msg;
        el.style.color = isError ? 'red' : 'black';
        el.style.display = 'block';
    }

    function hideMessages() {
        errorMessageDiv.style.display     = 'none';
        noResultsMessageDiv.style.display = 'none';
    }

    function switchView(view) {
        newsGrid.style.display         = view === 'news-grid' ? 'grid' : 'none';
        articleDetailView.style.display = view === 'detail'    ? 'block' : 'none';
        filterControlsDiv.style.display = view === 'news-grid' ? 'flex' : 'none';
    }

    function renderArticleGrid(articles) {
        if (!articles.length) {
            noResultsMessageDiv.style.display = 'block';
            return;
        }
        articles.forEach(article => {
            const card = document.createElement('div');
            card.className = 'news-card';
            let imageUrl = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
            card.innerHTML = `
                <img src="${imageUrl}" alt="" onerror="this.onerror=null;this.src='${DEFAULT_IMAGE}';">
                <div class="card-content">
                    <h6>${article.original_title || 'Untitled'}</h6>
                    <div class="caption">Published: ${article.published_at_formatted || 'Unknown'}</div>
                    <button>Read Article</button>
                </div>
            `;
            card.querySelector('button').addEventListener('click', () => showArticleDetail(article));
            newsGrid.appendChild(card);
        });
    }

    function renderTimeline(items) {
  // Clear out any old entries
  detailTimeline.innerHTML = '';
  if (items && items.length > 0) {
    items.forEach(e => {
      const entryDiv = document.createElement('div');
      entryDiv.innerHTML = `
        <p><strong>${e.year || ''} – ${e.title || ''}</strong></p>
        <p style="margin-top: 0.2em;">${e.summary || ''}</p>
      `;
      detailTimeline.appendChild(entryDiv);
    });
  } else {
    detailTimeline.innerHTML = `<p>No timeline entries available.</p>`;
  }
}

function renderGlossary(items) {
  // Clear out any old terms
  detailGlossary.innerHTML = '';
  if (items && items.length > 0) {
    items.forEach(e => {
      const entryDiv = document.createElement('div');
      entryDiv.innerHTML = `<strong>${e.word || '?'}:</strong> ${e.definition || ''}`;
      detailGlossary.appendChild(entryDiv);
    });
  } else {
    detailGlossary.innerHTML = `<p>No glossary terms available.</p>`;
  }
}
    function showArticleDetail(article) {
        detailTitle.textContent   = article.original_title || 'Untitled';
        detailCaption.textContent = `Source: ${article.source_name || 'Unknown'} | Published: ${article.published_at_formatted || 'Unknown'}`;
        detailImage.src           = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
        //new code next two lines
        detailImage.style.display = 'block';
        detailImage.onerror = () => { detailImage.onerror = null; detailImage.src = DEFAULT_IMAGE; };
        detailContent.textContent = article.article_content || 'Content not available.';

        detailLinkContainer.innerHTML = '';
        if (article.original_url && article.original_url !== '#') {
            const a = document.createElement('a');
            a.href    = article.original_url;
            a.textContent = 'Read Article Online';
            a.target  = '_blank';
            a.rel     = 'noopener noreferrer';
            a.className = 'read-more-button';
            detailLinkContainer.appendChild(a);
        }

        renderTimeline(article.historical_context || []);
        renderGlossary(article.glossary           || []);
        switchView('detail');
    }

    function populateFilterOptions() {
        const populateSelect = (selectEl, options) => {
            selectEl.innerHTML = '';
            options.forEach(opt => {
                const o = document.createElement('option');
                o.value = opt;
                o.textContent = opt;
                selectEl.appendChild(o);
            });
        };
        populateSelect(sortSelect,    ["Newest First", "Oldest First"]);
        categorySelect.innerHTML = '';

        const catPlaceholder = document.createElement('option');
        catPlaceholder.value       = '';
        catPlaceholder.textContent = 'All Categories';
        catPlaceholder.disabled    = true;
        catPlaceholder.selected    = currentFilters.category === '';
        categorySelect.appendChild(catPlaceholder);
        
        availableFilterOptions.categories.forEach(c => {
          const o = document.createElement('option');
          o.value       = c;
          o.textContent = c;
          categorySelect.appendChild(o);
        });
        monthSelect.innerHTML = '';

        const placeholder = document.createElement('option');
        placeholder.value       = '';
        placeholder.textContent = 'All Months';
        placeholder.disabled    = true;
        placeholder.selected    = currentFilters.month === '';
        monthSelect.appendChild(placeholder);
    
        availableFilterOptions.months.forEach(m => {
          const o = document.createElement('option');
          o.value       = m;
          o.textContent = m;
          monthSelect.appendChild(o);
        });
    }

    async function fetchFilterOptions() {
        try {
            const resp = await fetch(filterOptionsUrl);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const opts = await resp.json();

            // Always prepend the "All ..." sentinel
            const cats = opts.categories || [];
            const mths = opts.months     || [];

            availableFilterOptions = {
                categories: opts.categories || [],
                months:     opts.months || []
            };

            populateFilterOptions();
        } catch (err) {
            displayMessage(errorMessageDiv, `Could not load filter options: ${err.message}`, true);
        }
    }

    async function fetchAndRenderArticles(filters) {
        hideMessages();
        loadingIndicator.style.display = 'block';
        newsGrid.innerHTML             = '';

        const params = new URLSearchParams();
        if (filters.search)          params.append('search', filters.search);
        if (filters.sort_option)     params.append('sort',   filters.sort_option);

        if (filters.month && filters.month !== 'All Months') {
            // Split "YYYY - MonthName" → ["2025", "June"]
            const [year, monthName] = filters.month.split(' - ');
            const idx = new Date(`${monthName} 1, ${year}`).getMonth() + 1;
            const code = String(idx).padStart(2, '0');  // "06" for June
            params.append('month', `${year}-${code}`);
        }

        if (filters.category && filters.category !== 'All Categories') {
            params.append('category', filters.category);
        }

        try {
            const resp = await fetch(`${articlesUrl}?${params.toString()}`);
            loadingIndicator.style.display = 'none';
            if (!resp.ok) throw new Error(resp.status);
            const articles = await resp.json();
            renderArticleGrid(articles);
        } catch (err) {
            displayMessage(errorMessageDiv, `Failed to load articles: ${err.message}. Ensure backend is running.`, true);
        }
    }

    function handleFilterChange() {
        currentFilters.search      = searchInput.value.trim();
        currentFilters.sort_option = sortSelect.value;
        currentFilters.category    = categorySelect.value;
        currentFilters.month       = monthSelect.value;
        fetchAndRenderArticles(currentFilters);
    }

    // Wire up events
    sortSelect.addEventListener('change', handleFilterChange);
    categorySelect.addEventListener('change', handleFilterChange);
    monthSelect.addEventListener('change', handleFilterChange);
    searchInput.addEventListener('input', handleFilterChange);
    detailBackButton.addEventListener('click', () => switchView('news-grid'));

    // Kick things off
    (function init() {
        switchView('news-grid');
        loadingIndicator.style.display = 'block';
        fetchFilterOptions().then(() => {
            fetchAndRenderArticles(currentFilters);
        });
    })();
});
