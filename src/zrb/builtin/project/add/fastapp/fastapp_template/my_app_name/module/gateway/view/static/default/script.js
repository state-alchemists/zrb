// Hamburger menu functionality
const hamburgerMenu = document.querySelector('.hamburger-menu');
const layoutContainer = document.querySelector('.layout-container');

hamburgerMenu.addEventListener('click', function() {
    layoutContainer.classList.toggle('menu-active');
});

// Close menu when clicking outside
document.addEventListener('click', function(event) {
    if (!layoutContainer.contains(event.target) && !hamburgerMenu.contains(event.target)) {
        layoutContainer.classList.remove('menu-active');
    }
});

// Theme switcher functionality
const themeSelect = document.getElementById('theme-select');

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

function getSavedTheme() {
    return localStorage.getItem('theme') || 'auto';
}

const savedTheme = getSavedTheme();
setTheme(savedTheme);
themeSelect.value = savedTheme;

themeSelect.addEventListener('change', (e) => {
    setTheme(e.target.value);
});

function updateAutoTheme() {
    if (getSavedTheme() === 'auto') {
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    }
}

updateAutoTheme();
window.matchMedia('(prefers-color-scheme: dark)').addListener(updateAutoTheme);