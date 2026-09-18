/* ==========================================================================
   Forensic Lens — cases.js
   Runs on every page. Reads the active case id (CaseState, from api.js)
   and fills in the sidebar case chip + topbar with that case's info via
   Api.getCase(). Falls back to the "no case selected" markup already in
   the HTML if there's no active case or the request fails.

   NOTE: there is currently no case-creation/case-picker page in this
   project (create-case.html was never built), so createCase()/getCases()
   are wired here but have nothing to call them yet. Flagging this as a
   known gap rather than guessing at a UI for it.
   ========================================================================== */

(function () {
  const caseId = CaseState.getCurrentCaseId();

  const idEl = document.querySelector('[data-case-id]');
  const metaEl = document.querySelector('[data-case-meta]');
  const topbarIdEl = document.querySelector('[data-topbar-case-id]');
  const topbarDateEl = document.querySelector('[data-topbar-case-date]');
  const statusEl = document.querySelector('[data-case-status]');

  if (!caseId) {
    setStatus('No case selected');
    return;
  }

  Api.getCase(caseId)
    .then((data) => {
      if (idEl) idEl.textContent = data.id;
      if (metaEl) metaEl.textContent = data.description || data.name || '';
      if (topbarIdEl) topbarIdEl.textContent = data.id;
      if (topbarDateEl && data.created_at) {
        topbarDateEl.textContent = `Opened ${formatDate(data.created_at)}`;
      }
      setStatus('Loaded');
    })
    .catch((err) => {
      console.error('cases.js: failed to load active case', err);
      setStatus('Case unavailable');
    });

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function formatDate(iso) {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric'
      });
    } catch {
      return iso;
    }
  }
})();
