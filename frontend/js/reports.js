/* ==========================================================================
   Forensic Lens — reports.js
   Loads the structured report via Api.getReport() and renders it into
   the existing report sections. Section-visibility toggles and the
   print-based "export" are unchanged from before — they now just act
   on real content instead of static markup.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#report-loading');
  const emptyState = document.querySelector('#report-empty');
  const errorState = document.querySelector('#report-error');
  const populated = document.querySelector('#report-populated');
  const exportBtn = document.querySelector('#export-report');

  const caseId = CaseState.getCurrentCaseId();

  if (exportBtn) exportBtn.disabled = true;

  if (!caseId) {
    show(emptyState);
    return;
  }

  show(loadingState);

  Api.getReport(caseId)
    .then((report) => {
      show(populated);
      renderReport(report);
      if (exportBtn) exportBtn.disabled = false;
    })
    .catch((err) => {
      console.error('reports.js: failed to load report', err);
      show(errorState, err.message);
    });

  function renderReport(report) {
    setHtml('#report-evidence-list', listOrFallback(report.evidence_summary));
    setHtml('#report-timeline-list', listOrFallback(report.timeline_summary));
    setHtml('#report-location-list', listOrFallback(report.location_summary));

    const notes = document.querySelector('#report-notes');
    if (notes) notes.textContent = report.notes || 'No notes added yet.';

    document.querySelectorAll('.report-section-toggle').forEach((toggle) => {
      toggle.addEventListener('change', () => {
        const section = document.querySelector(toggle.dataset.target);
        if (section) section.style.display = toggle.checked ? '' : 'none';
      });
    });

    if (exportBtn) {
      exportBtn.addEventListener('click', () => window.print());
    }
  }

  // The report contract doesn't specify exact summary fields yet, so
  // this renders whatever the backend sends as a plain list rather than
  // assuming specific keys. Update this once the report shape is final.
  function listOrFallback(section) {
    if (!section) return '<li>Not available yet.</li>';
    if (Array.isArray(section)) {
      return section.map((line) => `<li>${escapeHtml(String(line))}</li>`).join('');
    }
    if (typeof section === 'object') {
      return Object.entries(section)
        .map(([key, value]) => `<li><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</li>`)
        .join('');
    }
    return `<li>${escapeHtml(String(section))}</li>`;
  }

  function show(el, message) {
    [loadingState, emptyState, errorState, populated].forEach((s) => {
      if (s) s.style.display = 'none';
    });
    if (el) {
      el.style.display = '';
      if (message && el === errorState) {
        const msgEl = el.querySelector('[data-error-message]');
        if (msgEl) msgEl.textContent = message;
      }
    }
  }

  function setHtml(selector, html) {
    const el = document.querySelector(selector);
    if (el) el.innerHTML = html;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
})();
