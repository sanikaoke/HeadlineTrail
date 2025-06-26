document.addEventListener('DOMContentLoaded', () => {
    // --- Get Data from the "Data Island" embedded in the HTML ---
    const dataScript = document.getElementById('articles-data');
    if (!dataScript) {
        console.error("Data island not found!");
        return;
    }
    const allArticles = JSON.parse(dataScript.textContent);

    // Create a map for quick lookups by article URL (our ID)
    const articlesMap = new Map(allArticles.map(article => [article.original_url, article]));
    
    // --- DOM Elements ---
    const articleDetailView = document.getElementById('article-detail');
    const filterControlsDiv = document.getElementById('filter-controls');
    const detailBackButton = document.getElementById('back-button');
    const detailTitle = document.getElementById('detail-title');
    const detailCaption = document.getElementById('detail-caption');
    const detailImage = document.getElementById('detail-image');
    const detailContent = document.getElementById('detail-content');
    const detailTimeline = document.getElementById('detail-timeline');
    const detailGlossary = document.getElementById('detail-glossary');
    const readMoreContainer = document.getElementById('read-more-container');

    const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80";

    function switchView(viewIdToShow) {
        document.getElementById('news-grid').style.display = 'none';
        document.getElementById('article-detail').style.display = 'none';
        
        const viewToShow = document.getElementById(viewIdToShow);
        if (viewToShow) {
            viewToShow.style.display = (viewIdToShow === 'news-grid') ? 'grid' : 'block';
        }
        filterControlsDiv.style.display = (viewIdToShow === 'news-grid') ? 'flex' : 'none';
        window.scrollTo(0, 0);
    }

    function showArticleDetail(article) {
        if (!article) return;

        detailTitle.textContent = article.original_title || 'Untitled';
        detailCaption.textContent = `Source: ${article.source || 'Unknown'} | Published: ${article.published_at_formatted || 'Unknown'}`;
        
        let imageUrl = article.article_url_to_image;
        detailImage.src = imageUrl || DEFAULT_IMAGE;
        detailImage.style.display = 'block';
        detailImage.onerror = () => { detailImage.src = DEFAULT_IMAGE; };

        detailContent.textContent = article.article_content || 'Content not available.';

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
                entryDiv.innerHTML = `<p><strong>${entry.year || '?'}: ${entry.title || 'Event'}</strong></p><p style="margin-top: 0.2em;">${entry.summary || ''}</p>`;
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

    // --- Add Event Listeners to the pre-built cards ---
    function initializeListeners() {
        const buttons = document.querySelectorAll('.news-card button');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                const articleId = button.dataset.articleId;
                const articleData = articlesMap.get(articleId);
                showArticleDetail(articleData);
            });
        });
    }

    // --- Initialize Listeners and Back Button ---
    initializeListeners();
    detailBackButton.addEventListener('click', () => switchView('news-grid'));

    // Note: Filtering has been removed in this simplified static version.
    // To add it back, you would need to write JavaScript that filters the 
    // `allArticles` array and re-renders the `news-grid` div's innerHTML.
});
