/* ==========================================================================
   Forensic Lens — analysis.js
   Renders the backend's deterministic correlation results on
   analysis.html.

   Fixed in this integration pass: this file read data.relationships and
   fields like shared_identifier / time_relationship, none of which the
   backend sends. The real response exposes `correlations`, each with
   correlation_id / related_event_ids / reason / rule / context. That
   translation lives in Shape.analysis().

   FORENSIC WORDING (project rule): this file displays only what the
   backend reports. A correlation is an observed pattern — closeness in
   time, a shared identifier, a location record near other activity. It
   is never phrased as a conclusion about conduct, intent or identity,
   and the backend's own disclaimer is always shown alongside it.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#analysis-loading');
  const emptyState = document.querySelector('#analysis-empty');
  const errorState = document.querySelector('#analysis-error');
  const populated = document.querySelector('#analysis-populated');
  if (!loadingState && !emptyState && !populated) return; // not this page

  const states = [loadingState, emptyState, errorState, populated];
  const listEl = document.querySelector('#correlation-list');
  const filterRow = document.querySelector('#analysis-filters');
  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    UI.showOnly(states, emptyState);
    return;
  }

  UI.showOnly(states, loadingState);

  Api.getAnalysis(caseId)
    .then((raw) => {
      const data = Shape.analysis(raw);
      if (!data.totalCorrelations) {
        UI.showOnly(states, emptyState);
        return;
      }
      UI.showOnly(states, populated);
      renderSummary(data);
      renderCorrelations(data.items);
      wireFilters(data.items);
    })
    .catch((err) => {
      console.error('analysis.js: failed to load analysis', err);
      UI.showOnly(states, errorState, err.message);
    });

  function renderSummary(data) {
    UI.setText('#analysis-total-events', String(data.totalEvents));
    UI.setText('#analysis-total-correlations', String(data.totalCorrelations));
    UI.setText('#analysis-window',
      data.timeWindowMinutes !== null ? `${data.timeWindowMinutes} minutes` : '—');
    UI.setText('#analysis-disclaimer', data.disclaimer);

    UI.setHtml('#analysis-by-rule', Object.entries(data.byRule)
      .map(([rule, count]) => `<li><strong>${UI.escapeHtml(Shape.ruleLabel(rule))}:</strong> ${UI.escapeHtml(count)}</li>`)
      .join('') || '<li>Nothing recorded.</li>');
  }

  function renderCorrelations(items) {
    if (!listEl) return;
    listEl.innerHTML = items.map((item) => `
      <div class="panel correlation-item" data-rule="${UI.escapeHtml(item.rule)}">
        <div class="correlation-head">
          <span class="mono">${UI.escapeHtml(item.id)}</span>
          <span class="chip active">${UI.escapeHtml(item.ruleLabel)}</span>
        </div>
        <p class="sub">${UI.escapeHtml(item.reason)}</p>
        <ul class="report-summary-list">
          ${item.context.map(([k, v]) => `<li><strong>${UI.escapeHtml(k)}:</strong> ${UI.escapeHtml(v)}</li>`).join('')}
          <li><strong>Related event ids:</strong> <span class="mono">${UI.escapeHtml(item.eventIds.join(', '))}</span></li>
        </ul>
      </div>
    `).join('');
  }

  function wireFilters(items) {
    if (!filterRow) return;
    filterRow.style.display = '';
    filterRow.querySelectorAll('.chip[data-rule-filter]').forEach((chip) => {
      chip.addEventListener('click', () => {
        filterRow.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        const filter = chip.dataset.ruleFilter;
        listEl.querySelectorAll('.correlation-item').forEach((el) => {
          el.style.display = (filter === 'all' || el.dataset.rule === filter) ? '' : 'none';
        });
      });
    });
  }
})();
