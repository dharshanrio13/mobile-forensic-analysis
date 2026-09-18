/* ==========================================================================
   Forensic Lens — case-manager.js
   Powers cases.html: create a case, list existing cases, and pick the
   one the rest of the app works against.

   This closes the gap the old cases.js flagged — createCase()/getCases()
   existed in api.js but nothing ever called them, and the only way to
   set a case was typing a raw id into a box on the evidence page.
   ========================================================================== */

(function () {
  const form = document.querySelector('#create-case-form');
  if (!form) return; // not this page

  const nameInput = document.querySelector('#case-name');
  const descInput = document.querySelector('#case-description');
  const createBtn = document.querySelector('#create-case-btn');
  const formError = document.querySelector('#create-case-error');
  const listEl = document.querySelector('#case-list');
  const listEmpty = document.querySelector('#case-list-empty');
  const listError = document.querySelector('#case-list-error');
  const healthEl = document.querySelector('#backend-status');

  checkBackend();
  loadCases();

  createBtn.addEventListener('click', () => {
    const name = nameInput.value.trim();
    const description = descInput.value.trim();

    if (!name || !description) {
      showFormError('Both a name and a description are required.');
      return;
    }

    showFormError('');
    createBtn.disabled = true;
    createBtn.textContent = 'Creating…';

    Api.createCase(name, description)
      .then((created) => {
        CaseState.setCurrentCaseId(created.id);
        nameInput.value = '';
        descInput.value = '';
        loadCases();
      })
      .catch((err) => {
        console.error('case-manager.js: create failed', err);
        showFormError(err.message || 'Could not create the case.');
      })
      .finally(() => {
        createBtn.disabled = false;
        createBtn.textContent = 'Create case';
      });
  });

  function checkBackend() {
    if (!healthEl) return;
    Api.health()
      .then((res) => {
        healthEl.textContent = res && res.status === 'ok' ? 'Backend connected' : 'Backend responded unexpectedly';
      })
      .catch(() => {
        healthEl.textContent = 'Backend unreachable';
      });
  }

  function loadCases() {
    Api.getCases()
      .then((cases) => {
        if (listError) listError.style.display = 'none';
        renderCases(cases || []);
      })
      .catch((err) => {
        console.error('case-manager.js: list failed', err);
        if (listEl) listEl.innerHTML = '';
        if (listEmpty) listEmpty.style.display = 'none';
        if (listError) {
          listError.style.display = '';
          const msg = listError.querySelector('[data-error-message]');
          if (msg) msg.textContent = err.message || '';
        }
      });
  }

  function renderCases(cases) {
    if (!listEl) return;
    const activeId = CaseState.getCurrentCaseId();

    if (!cases.length) {
      listEl.innerHTML = '';
      if (listEmpty) listEmpty.style.display = '';
      return;
    }
    if (listEmpty) listEmpty.style.display = 'none';

    listEl.innerHTML = cases.map((c) => `
      <div class="case-row${c.id === activeId ? ' active' : ''}" data-case-row="${UI.escapeHtml(c.id)}">
        <div class="case-row-main">
          <div class="case-row-name">${UI.escapeHtml(c.name)}</div>
          <div class="case-row-desc">${UI.escapeHtml(c.description)}</div>
          <div class="case-row-id mono">${UI.escapeHtml(c.id)}</div>
        </div>
        <div class="case-row-side">
          <div class="case-row-date">${UI.escapeHtml(UI.formatDate(c.created_at))}</div>
          <button type="button" class="btn ${c.id === activeId ? 'btn-secondary' : 'btn-primary'}"
                  data-select-case="${UI.escapeHtml(c.id)}">
            ${c.id === activeId ? 'Active' : 'Open case'}
          </button>
        </div>
      </div>
    `).join('');

    listEl.querySelectorAll('[data-select-case]').forEach((btn) => {
      btn.addEventListener('click', () => {
        CaseState.setCurrentCaseId(btn.dataset.selectCase);
        window.location.href = 'dashboard.html';
      });
    });
  }

  function showFormError(message) {
    if (!formError) return;
    formError.textContent = message;
    formError.style.display = message ? '' : 'none';
  }
})();
