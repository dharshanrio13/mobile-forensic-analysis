/* ==========================================================================
   Forensic Lens — reports.js
   Loads the structured forensic report via Api.getReport() and renders
   its sections. Section-visibility toggles and the print-based export
   work as before, now against real content.

   Fixed in this integration pass: this file read report.evidence_summary,
   report.timeline_summary, report.location_summary and report.notes —
   none of which the backend sends. The real sections are disclaimer,
   case_information, observed_evidence, calculated_analysis
   {timeline_summary, location_summary, communication_summary},
   potentially_related_events and report_integrity. That mapping lives in
   Shape.report().

   The backend's disclaimer and the "potentially related" note are
   rendered verbatim — they are the wording that keeps this a record of
   observed evidence rather than a finding.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#report-loading');
  const emptyState = document.querySelector('#report-empty');
  const errorState = document.querySelector('#report-error');
  const populated = document.querySelector('#report-populated');
  const states = [loadingState, emptyState, errorState, populated];
  const exportBtn = document.querySelector('#export-report');

  const caseId = CaseState.getCurrentCaseId();

  if (exportBtn) {
    exportBtn.disabled = true;
    exportBtn.addEventListener('click', () => window.print());
  }

  wireSectionToggles();

  if (!caseId) {
    UI.showOnly(states, emptyState);
    return;
  }

  UI.showOnly(states, loadingState);

  Api.getReport(caseId)
    .then((raw) => {
      UI.showOnly(states, populated);
      renderReport(Shape.report(raw));
      if (exportBtn) exportBtn.disabled = false;
    })
    .catch((err) => {
      console.error('reports.js: failed to load report', err);
      UI.showOnly(states, errorState, err.message);
    });

  function renderReport(report) {
    UI.setText('#report-disclaimer', report.disclaimer);
    UI.setHtml('#report-case-list', UI.pairsToList(report.caseInformation));

    UI.setHtml('#report-evidence-list', evidenceList(report.evidence));
    UI.setHtml('#report-timeline-list', UI.pairsToList(report.timelineSummary));
    UI.setHtml('#report-location-list', locationList(report.locationSummary));
    UI.setHtml('#report-communication-list', UI.pairsToList(report.communicationSummary));
    UI.setHtml('#report-related-list', relatedList(report.related));
    UI.setHtml('#report-integrity-list', UI.pairsToList(report.integrity));

    const note = document.querySelector('#report-related-note');
    if (note) note.textContent = report.related.note;
  }

  // OBSERVED EVIDENCE — a restatement of what was uploaded and parsed.
  function evidenceList(evidence) {
    if (!evidence.totalItems) return '<li>No evidence registered for this case.</li>';
    const counts = Object.entries(evidence.countsByType)
      .map(([type, count]) => `${type}: ${count}`)
      .join(' · ');
    const header = `<li><strong>Total items:</strong> ${UI.escapeHtml(evidence.totalItems)}${counts ? ` (${UI.escapeHtml(counts)})` : ''}</li>`;
    const items = evidence.items
      .map((item) => `<li><span class="mono">${UI.escapeHtml(item.filename)}</span> — ${UI.escapeHtml(item.evidence_type)}</li>`)
      .join('');
    return header + items;
  }

  // CALCULATED ANALYSIS — recorded points, stated as recorded.
  function locationList(summary) {
    if (!summary.count) return '<li>No location records.</li>';
    const header = `<li><strong>Location records:</strong> ${UI.escapeHtml(summary.count)}</li>`;
    const points = summary.points
      .map((p) => `<li><span class="mono">${UI.escapeHtml(UI.formatTimestamp(p.timestamp))}</span> — ${UI.escapeHtml(p.latitude)}, ${UI.escapeHtml(p.longitude)}${p.label ? ` (${UI.escapeHtml(p.label)})` : ''}</li>`)
      .join('');
    return header + points;
  }

  // POTENTIALLY RELATED EVENTS — candidates for review, never findings.
  function relatedList(related) {
    if (!related.count) return '<li>No potentially related events were identified.</li>';
    return related.items
      .map((item) => `<li><span class="mono">${UI.escapeHtml(item.correlation_id)}</span> — ${UI.escapeHtml(item.reason)}</li>`)
      .join('');
  }

  function wireSectionToggles() {
    document.querySelectorAll('.report-section-toggle').forEach((toggle) => {
      toggle.addEventListener('change', () => {
        const section = document.querySelector(toggle.dataset.target);
        if (section) section.style.display = toggle.checked ? '' : 'none';
      });
    });
  }
})();
