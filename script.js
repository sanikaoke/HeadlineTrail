document.addEventListener('DOMContentLoaded', () => {
  const newsGrid            = document.getElementById('news-grid');
  const articleDetailView   = document.getElementById('article-detail');
  const filterControlsDiv   = document.getElementById('filter-controls');
  const loadingIndicator    = document.getElementById('loading-indicator');
  const errorMessageDiv     = document.getElementById('error-message');
  const noResultsMessageDiv = document.getElementById('no-results-message');

  const searchInput    = document.getElementById('search-input');
  const sortSelect     = document.getElementById('sort-select');
  const categorySelect = document.getElementById('category-select');
  const monthSelect    = document.getElementById('month-select');

  const detailBackButton    = document.getElementById('back-button');
  const detailTitle         = document.getElementById('detail-title');
  const detailCaption       = document.getElementById('detail-caption');
  const detailImage         = document.getElementById('detail-image');
  const detailContent       = document.getElementById('detail-content');
  const detailTimeline      = document.getElementById('detail-timeline');
  const detailGlossary      = document.getElementById('detail-glossary');
  const detailLinkContainer = document.getElementById('detail-link-container');

  const backendBaseUrl   = 'https://headlinetrail.onrender.com';
  const articlesUrl      = `${backendBaseUrl}/articles`;
  const filterOptionsUrl = `${backendBaseUrl}/filter-options`;

  let currentFilters = {
    search: '',
    sort_option: 'Newest First',
    category: 'All Categories',
    month: 'All Months'
  };

  let availableFilterOptions = { categories: [], months: [] };

  const IMAGE_COLUMN_NAME = "article_url_to_image";
  const DEFAULT_IMAGE     = "https://images.unsplash.com/photo-1516116216624-53e697fedbe0?auto=format&fit=crop&w=600&q=80";

  function hideMessages() {
    errorMessageDiv.style.display = 'none';
    noResultsMessageDiv.style.display = 'none';
  }

  function switchView(view) {
    newsGrid.style.display          = view === 'news-grid' ? 'grid' : 'none';
    articleDetailView.style.display = view === 'detail'    ? 'block' : 'none';
    filterControlsDiv.style.display = view === 'news-grid' ? 'flex' : 'none';
  }

  function renderArticleGrid(articles) {
    newsGrid.innerHTML = '';
    if (!articles || !articles.length) {
      noResultsMessageDiv.style.display = 'block';
      return;
    }
    noResultsMessageDiv.style.display = 'none';

    articles.forEach(article => {
      const card = document.createElement('div');
      card.className = 'news-card';
      const imageUrl = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;

      card.innerHTML = `
        <img src="${imageUrl}" alt="" onerror="this.onerror=null;this.src='${DEFAULT_IMAGE}'">
        <div class="card-content">
          <h6>${article.original_title || 'Untitled'}</h6>
          <div class="caption">By ${article.author || 'Unknown author'} | Published: ${article.published_at_formatted || 'Unknown'}</div>
          <button>Read Article</button>
        </div>
      `;
      card.querySelector('button').addEventListener('click', () => showArticleDetail(article));
      newsGrid.appendChild(card);
    });
  }

  function renderTimeline(items) {
    detailTimeline.innerHTML = '';
    if (items && items.length) {
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
    if (items && items.length) {
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
    if (article.summarized_content && article.summarized_content.trim()) {
      const bulletPoints = article.summarized_content
        .split('\n')
        .map(s => s.trim().replace(/^\-\s*/, ''))
        .filter(Boolean);

      const summaryHTML = `
        <h3>Article Summary</h3>
        <ul style="padding-left:1.2em; margin-top:0.5em;">
          ${bulletPoints.map(p => `<li>${p}</li>`).join('')}
        </ul>
      `;
      detailContent.insertAdjacentHTML('beforeend', summaryHTML);
    } else {
      detailContent.innerHTML = `<p>No summary available.</p>`;
    }
  }

  function showArticleDetail(article) {
    // reset
    detailContent.innerHTML = '';
    detailTimeline.innerHTML = '';
    detailGlossary.innerHTML = '';
    detailLinkContainer.innerHTML = '';

    // header/meta
    detailTitle.textContent = article.original_title || 'Untitled';
    detailCaption.innerHTML = [
      `By ${article.author || 'Unknown author'}`,
      `Source: ${article.source || 'Unknown'}`,
      `Published: ${article.published_at_formatted || 'Unknown'}`
    ].join(' | ');

    // image
    detailImage.src = article[IMAGE_COLUMN_NAME] || DEFAULT_IMAGE;
    detailImage.style.display = 'block';
    detailImage.onerror = () => { detailImage.onerror = null; detailImage.src = DEFAULT_IMAGE; };

    // link
    if (article.original_url && article.original_url !== '#') {
      const a = document.createElement('a');
      a.href = article.original_url;
      a.textContent = 'Read Article Online';
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.className = 'read-more-button';
      detailLinkContainer.appendChild(a);
    }

    // render sections
    renderQuickSummary(article);
    renderTimeline(article.historical_context || []);
    renderGlossary(article.glossary || []);

    // ⬆️ Scroll to top when opening an article
    window.scrollTo(0, 0);

    switchView('detail');
  }

  function populateFilterOptions() {
    // Sort select (ensure all options present)
    sortSelect.innerHTML = '';
    ['Newest First', 'Oldest First', 'A-Z', 'Z-A'].forEach(opt => {
      const o = document.createElement('option');
      o.value = opt; o.textContent = opt;
      if (opt === currentFilters.sort_option) o.selected = true;
      sortSelect.appendChild(o);
    });

    // Category select: include "All Categories" only once and set it as default
    categorySelect.innerHTML = '';
    const catAll = document.createElement('option');
    catAll.value = 'All Categories';
    catAll.textContent = 'All Categories';
    categorySelect.appendChild(catAll);

    (availableFilterOptions.categories || [])
      .filter(c => c && c !== 'All Categories')
      .forEach(cat => {
        const o = document.createElement('option');
        o.value = cat; o.textContent = cat;
        categorySelect.appendChild(o);
      });
    categorySelect.value = currentFilters.category || 'All Categories';

    // Month select: include "All Months" only once and set it as default
    monthSelect.innerHTML = '';
    const monthAll = document.createElement('option');
    monthAll.value = 'All Months';
    monthAll.textContent = 'All Months';
    monthSelect.appendChild(monthAll);

    (availableFilterOptions.months || [])
      .filter(m => m && m !== 'All Months')
      .forEach(m => {
        const o = document.createElement('option');
        o.value = m; o.textContent = m;
        monthSelect.appendChild(o);
      });
    monthSelect.value = currentFilters.month || 'All Months';
  }

  async function fetchFilterOptions() {
    try {
      const resp = await fetch(filterOptionsUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      availableFilterOptions = {
        categories: data.categories || [],
        months: data.months || []
      };
      populateFilterOptions();
    } catch (err) {
      console.warn('filter options fetch failed:', err);
      // still populate with defaults so UI isn’t empty
      populateFilterOptions();
    }
  }

  async function fetchAndRenderArticles(filters) {
    hideMessages();
    loadingIndicator.style.display = 'block';
    newsGrid.innerHTML = '';

    const params = new URLSearchParams();
    if (filters.search)      params.append('search', filters.search);
    if (filters.sort_option) params.append('sort',   filters.sort_option);
    if (filters.category && filters.category !== 'All Categories') {
      params.append('category', filters.category);
    }
    if (filters.month && filters.month !== 'All Months') {
      // Backend expects YYYY-MM; our dropdown shows "YYYY - MonthName"
      // Convert if needed:
      if (/^\d{4}\s-\s[A-Za-z]+$/.test(filters.month)) {
        const [year, monthName] = filters.month.split(' - ');
        const idx  = new Date(`${monthName} 1, ${year}`).getMonth() + 1;
        const code = String(idx).padStart(2, '0');
        params.append('month', `${year}-${code}`);
      } else {
        // If it’s already in YYYY-MM form, just pass it through
        params.append('month', filters.month);
      }
    }

    try {
      const resp = await fetch(`${articlesUrl}?${params.toString()}`);
      loadingIndicator.style.display = 'none';
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const articles = await resp.json();
      renderArticleGrid(articles);

      // ⬆️ After refresh, ensure the grid starts at the top
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      loadingIndicator.style.display = 'none';
      errorMessageDiv.textContent = `Failed to load articles: ${err.message}`;
      errorMessageDiv.style.display = 'block';
    }
  }

  function handleFilterChange() {
    currentFilters = {
      search:      searchInput.value.trim(),
      sort_option: sortSelect.value,
      category:    categorySelect.value || 'All Categories',
      month:       monthSelect.value || 'All Months'
    };
    fetchAndRenderArticles(currentFilters);
  }

  // Wire up events (update filters FIRST, then fetch)
  sortSelect.addEventListener('change', handleFilterChange);
  categorySelect.addEventListener('change', handleFilterChange);
  monthSelect.addEventListener('change', handleFilterChange);
  searchInput.addEventListener('input', () => {
    // debounce a hair to avoid hammering the backend
    clearTimeout(searchInput._t);
    searchInput._t = setTimeout(handleFilterChange, 250);
  });

  detailBackButton.addEventListener('click', () => {
    switchView('news-grid');
    // ⬆️ Scroll to top when returning to the grid
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Init
  (async function init() {
    switchView('news-grid');
    loadingIndicator.style.display = 'block';
    await fetchFilterOptions();                  // populate dropdowns first
    await fetchAndRenderArticles(currentFilters); // then initial list
  })();
});
