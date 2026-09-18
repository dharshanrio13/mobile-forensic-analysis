/* ==========================================================================
   Forensic Lens — ui.js
   Tiny shared DOM helpers used by every page script. Previously each
   file carried its own private copies of escapeHtml/formatTimestamp/
   show(); they're identical, so they live here once instead.
   No API calls, no state.
   ========================================================================== */

const UI = (function () {
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str === null || str === undefined ? '' : String(str);
    return div.innerHTML;
  }

  function formatTimestamp(iso) {
    const parsed = Date.parse(iso);
    if (!Number.isFinite(parsed)) return iso || '—';
    return new Date(parsed).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
  }

  function formatTime(iso) {
    const parsed = Date.parse(iso);
    if (!Number.isFinite(parsed)) return iso || '—';
    return new Date(parsed).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function formatDate(iso) {
    const parsed = Date.parse(iso);
    if (!Number.isFinite(parsed)) return iso || '—';
    return new Date(parsed).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  }

  // Shows one of a set of mutually exclusive state containers
  // (loading / empty / error / populated) and hides the rest.
  function showOnly(states, target, message) {
    states.forEach((s) => { if (s) s.style.display = 'none'; });
    if (!target) return;
    target.style.display = '';
    if (message) {
      const msgEl = target.querySelector('[data-error-message]');
      if (msgEl) msgEl.textContent = message;
    }
  }

  function setText(selector, text) {
    const el = document.querySelector(selector);
    if (el) el.textContent = text;
  }

  function setHtml(selector, html) {
    const el = document.querySelector(selector);
    if (el) el.innerHTML = html;
  }

  // Renders [label, value] pairs as report-summary-list <li> items.
  function pairsToList(pairs) {
    if (!pairs || !pairs.length) return '<li>Nothing recorded.</li>';
    return pairs
      .map(([label, value]) => `<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value)}</li>`)
      .join('');
  }

  return { escapeHtml, formatTimestamp, formatTime, formatDate, showOnly, setText, setHtml, pairsToList };
})();
