/* ==========================================================================
   Forensic Lens — navigation.js
   Highlights the current page's sidebar item based on the file name.
   No routing, no API calls — pages are plain linked .html files.
   Unmodified as part of this integration pass (already correctly UI-only).
   ========================================================================== */

(function () {
  const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';

  document.querySelectorAll('.nav-item[href]').forEach((item) => {
    const href = item.getAttribute('href');
    if (href === currentPage) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  document.querySelectorAll('.nav-item.disabled').forEach((item) => {
    item.addEventListener('click', (e) => e.preventDefault());
  });
})();
