/* ==========================================================================
   Forensic Lens — dashboard.js
   Loads the case overview from the backend via api.js (getTimeline,
   getLocations, getCommunications) and renders the summary cards +
   recent-activity list. Shows loading/empty/error states rather than
   ever fabricating numbers.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#dashboard-loading');
  const emptyState = document.querySelector('#dashboard-empty');
  const errorState = document.querySelector('#dashboard-error');
  const populated = document.querySelector('#dashboard-populated');

  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    show(emptyState);
    return;
  }

  show(loadingState);

  Promise.all([
    Api.getTimeline(caseId).catch(() => []),
    Api.getLocations(caseId).catch(() => []),
    Api.getCommunications(caseId).catch(() => null)
  ])
    .then(([timeline, locations, communications]) => {
      show(populated);
      renderStats(timeline, locations, communications);
      renderRecentActivity(timeline);
      addPressedEffect();
    })
    .catch((err) => {
      console.error('dashboard.js: failed to load case data', err);
      show(errorState, err.message);
    });

  function renderStats(timeline, locations, communications) {
    const messageCount = communications && Array.isArray(communications.messages) ? communications.messages.length : null;
    const callCount = communications && Array.isArray(communications.calls) ? communications.calls.length : null;

    setText('#stat-messages-calls',
      messageCount !== null || callCount !== null
        ? `${messageCount ?? 0} messages · ${callCount ?? 0} calls logged`
        : 'No communications data yet');

    setText('#stat-timeline-count', `${timeline.length} events recorded`);
    setText('#stat-location-count', `${locations.length} points recorded`);
  }

  function renderRecentActivity(timeline) {
    const list = document.querySelector('#recent-activity-list');
    if (!list) return;
    list.innerHTML = '';

    if (!timeline.length) {
      list.innerHTML = '<div class="empty-note">No events recorded yet.</div>';
      return;
    }

    timeline.slice(0, 5).forEach((event) => {
      const row = document.createElement('div');
      row.className = 'activity-row';
      row.innerHTML = `
        <span class="t mono">${escapeHtml(formatTime(event.timestamp))}</span>
        <span class="d">${escapeHtml(event.description || event.event_type || 'Event recorded')}</span>
      `;
      list.appendChild(row);
    });
  }

  function addPressedEffect() {
    document.querySelectorAll('.module-card:not(.disabled)').forEach((card) => {
      card.addEventListener('mousedown', () => card.style.transform = 'scale(0.99)');
      card.addEventListener('mouseup', () => card.style.transform = '');
      card.addEventListener('mouseleave', () => card.style.transform = '');
    });
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

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    } catch {
      return iso || '—';
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
});
