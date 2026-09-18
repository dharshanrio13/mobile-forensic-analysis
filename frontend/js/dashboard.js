/* ==========================================================================
   Forensic Lens — dashboard.js
   Loads the case overview from the backend (timeline, locations,
   communications, evidence) and renders the summary cards + recent
   activity. Shows loading/empty/error states rather than fabricating
   numbers.

   Fixed in this integration pass:
     1. The IIFE was never invoked (it ended with `})` instead of `})();`),
        so this file did nothing at all.
     2. It read communications.calls / .messages — fields the backend
        does not send. All backend-shape handling now goes through
        Shape.dashboard() in shape.js.
     3. dashboard.html didn't load api.js, so CaseState/Api were
        undefined here. The page now loads them.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#dashboard-loading');
  const emptyState = document.querySelector('#dashboard-empty');
  const errorState = document.querySelector('#dashboard-error');
  const populated = document.querySelector('#dashboard-populated');
  const states = [loadingState, emptyState, errorState, populated];

  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    UI.showOnly(states, emptyState);
    return;
  }

  UI.showOnly(states, loadingState);

  Promise.all([
    Api.getTimeline(caseId),
    Api.getLocations(caseId),
    Api.getCommunications(caseId),
    Api.getEvidence(caseId)
  ])
    .then(([timeline, locations, communications, evidence]) => {
      const stats = Shape.dashboard(timeline, locations, communications, evidence);
      UI.showOnly(states, populated);
      renderStats(stats);
      renderRecentActivity(stats.recent);
      addPressedEffect();
    })
    .catch((err) => {
      console.error('dashboard.js: failed to load case data', err);
      UI.showOnly(states, errorState, err.message);
    });

  function renderStats(stats) {
    UI.setText('#stat-evidence-count',
      stats.fileCount ? `${stats.fileCount} evidence files parsed` : 'No evidence uploaded yet');
    UI.setText('#stat-evidence-meta',
      stats.packageCount
        ? `${stats.packageCount} package${stats.packageCount === 1 ? '' : 's'} · ${stats.errorCount} record(s) failed to parse`
        : 'Upload a simulated evidence .zip to begin');

    UI.setText('#stat-timeline-count', `${stats.eventCount} events recorded`);
    UI.setText('#stat-timeline-meta', spanText(stats));

    UI.setText('#stat-location-count', `${stats.locationCount} points recorded`);
    UI.setText('#stat-location-meta',
      stats.locationCount ? 'Plotted on the location map' : 'No location records');

    UI.setText('#stat-comms-count', `${stats.callCount} calls · ${stats.messageCount} messages`);
    UI.setText('#stat-comms-meta',
      stats.callCount + stats.messageCount ? 'Observed communication records' : 'No communications recorded');

    UI.setText('#stat-report-meta',
      stats.eventCount ? 'Generated from observed evidence' : 'Nothing to report yet');

    const device = stats.deviceInfo;
    UI.setText('#device-summary', device
      ? Object.entries(device).map(([k, v]) => `${k}: ${v}`).join(' · ')
      : 'No device.json was included in the uploaded evidence.');
  }

  function spanText(stats) {
    if (!stats.earliest || !stats.latest) return 'No events yet';
    return `Spans ${UI.formatDate(stats.earliest)} – ${UI.formatDate(stats.latest)}`;
  }

  function renderRecentActivity(recent) {
    const list = document.querySelector('#recent-activity-list');
    if (!list) return;
    list.innerHTML = '';

    if (!recent.length) {
      list.innerHTML = '<div class="empty-note">No events recorded yet.</div>';
      return;
    }

    recent.forEach((event) => {
      const row = document.createElement('div');
      row.className = 'activity-row';
      row.innerHTML = `
        <span class="t mono">${UI.escapeHtml(UI.formatTime(event.timestamp))}</span>
        <span class="d">${UI.escapeHtml(event.description || event.event_type || 'Event recorded')}</span>
      `;
      list.appendChild(row);
    });
  }

  function addPressedEffect() {
    document.querySelectorAll('.module-card:not(.disabled)').forEach((card) => {
      card.addEventListener('mousedown', () => { card.style.transform = 'scale(0.99)'; });
      card.addEventListener('mouseup', () => { card.style.transform = ''; });
      card.addEventListener('mouseleave', () => { card.style.transform = ''; });
    });
  }
})();
