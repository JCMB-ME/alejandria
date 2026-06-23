/* Theme initialization — runs before SvelteKit hydrates to prevent FOUC.
 * Externalized from app.html so it can be served as a same-origin script
 * (which the Content-Security-Policy allows), rather than an inline script
 * (which CSP would block).
 */
(function () {
  try {
    var t = localStorage.getItem('alejandria-theme');
    if (!t) {
      t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    if (t === 'light' || t === 'dark' || t === 'sepia') {
      document.documentElement.setAttribute('data-theme', t);
      document.documentElement.classList.toggle('dark', t === 'dark');
    } else {
      var customs = JSON.parse(localStorage.getItem('alejandria-custom-themes') || '[]');
      var found = customs.find(function (c) { return c.id === t; });
      if (found) {
        document.documentElement.setAttribute('data-theme', found.base);
        document.documentElement.classList.toggle('dark', found.base === 'dark');
        var colors = found.colors;
        document.documentElement.style.setProperty('--bg', colors.bg);
        document.documentElement.style.setProperty('--surface', colors.surface);
        document.documentElement.style.setProperty('--border', colors.border);
        document.documentElement.style.setProperty('--text', colors.text);
        document.documentElement.style.setProperty('--accent', colors.accent);
        document.documentElement.style.setProperty('--elevated', 'color-mix(in srgb, var(--surface) 92%, var(--text) 8%)');
        document.documentElement.style.setProperty('--text-muted', 'color-mix(in srgb, var(--text) 70%, var(--bg) 30%)');
        document.documentElement.style.setProperty('--text-soft', 'color-mix(in srgb, var(--text) 50%, var(--bg) 50%)');
        document.documentElement.style.setProperty('--accent-hover', 'color-mix(in srgb, var(--accent) 85%, var(--text) 15%)');
        document.documentElement.style.setProperty('--link', 'var(--accent)');
      }
    }
  } catch (e) {}
})();
