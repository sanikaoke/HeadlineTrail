document.addEventListener('DOMContentLoaded', () => {
    const backButton = document.getElementById('back-button');

    if (backButton) {
        backButton.addEventListener('click', () => {
            // Go back to the main page (index.html)
            window.location.href = '/';
        });
    }
});