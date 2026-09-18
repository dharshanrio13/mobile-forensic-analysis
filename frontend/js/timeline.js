/* ==========================================================================
   Forensic Lens — timeline.js
   Fetches this case's events via Api.getTimeline() and renders the
   .tl-item list itself (previously this assumed items were already in
   the HTML). Filtering and detail-panel selection work the same as
   before, just operating on rendered-from-data nodes now.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#timeline-loading');
  const emptyState = document.querySelector('#timeline-empty');
  const errorState = document.querySelector('#timeline-error');
  const listEl = document.querySelector('#timeline-list');
  const filterRow = document.querySelector('#timeline-filters');
  const detailPanel = document.querySelector('#event-detail');

  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    show(emptyState);
    return;
  }

  show(loadingState);

  Api.getTimeline(caseId)
    .then((events) => {
      const nonLocationEvents = events.filter((evt) => !isLocationEvent(evt));
      if (!nonLocationEvents.length) {
        show(emptyState);
        return;
      }
      show(listEl);
      if (filterRow) filterRow.style.display = '';
      renderEvents(nonLocationEvents);
      wireFilters(nonLocationEvents);
    })
    .catch((err) => {
      console.error('timeline.js: failed to load timeline', err);
      show(errorState, err.message);
    });

  // Location events have their own dedicated view (locations.html) with a
  // real map — showing them again here would just be duplicate, out-of-
  // place data, so they're excluded before anything gets rendered.
  function isLocationEvent(evt) {
    const tag = `${evt.category || ''} ${evt.event_type || ''}`.toLowerCase();
    return tag.includes('location') || tag.includes('gps');
  }

  function renderEvents(events) {
    listEl.innerHTML = '';
    events.forEach((evt, i) => {
      const item = document.createElement('div');
      item.className = 'tl-item';
      item.dataset.type = evt.category || evt.event_type || 'other';
      item.innerHTML = `
        <span class="tl-dot"></span>
        <div class="tl-head">
          <span class="tl-time mono">${escapeHtml(formatTimestamp(evt.timestamp))}</span>
          <span class="tl-type">${escapeHtml(evt.category || evt.event_type || '—')}</span>
        </div>
        <div class="tl-desc">${escapeHtml(evt.description || '—')}</div>
        <div class="tl-source">${escapeHtml(evt.source || '—')}</div>
      `;
      item.addEventListener('click', () => selectItem(item, evt));
      listEl.appendChild(item);
      if (i === 0) selectItem(item, evt);
    });
  }

  function wireFilters(events) {
    if (!filterRow) return;
    filterRow.querySelectorAll('.chip[data-filter]').forEach((chip) => {
      chip.addEventListener('click', () => {
        filterRow.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        const filter = chip.dataset.filter;
        listEl.querySelectorAll('.tl-item').forEach((item) => {
          item.style.display = (filter === 'all' || item.dataset.type === filter) ? '' : 'none';
        });
      });
    });
  }

  function selectItem(item, evt) {
    listEl.querySelectorAll('.tl-item').forEach((i) => i.classList.remove('selected'));
    item.classList.add('selected');
    if (!detailPanel) return;
    detailPanel.innerHTML = `
      <div class="detail-field"><div class="k">Time</div><div class="v mono">${escapeHtml(formatTimestamp(evt.timestamp))}</div></div>
      <div class="detail-field"><div class="k">Type</div><div class="v">${escapeHtml(evt.category || evt.event_type || '—')}</div></div>
      <div class="detail-field"><div class="k">Description</div><div class="v">${escapeHtml(evt.description || '—')}</div></div>
      <div class="detail-field"><div class="k">Source</div><div class="v">${escapeHtml(evt.source || '—')}</div></div>
    `;
  }

  function show(el, message) {
    [loadingState, emptyState, errorState, listEl].forEach((s) => {
      if (s) s.style.display = 'none';
    });
    if (filterRow && el !== listEl) filterRow.style.display = 'none';
    if (el) {
      el.style.display = '';
      if (message && el === errorState) {
        const msgEl = el.querySelector('[data-error-message]');
        if (msgEl) msgEl.textContent = message;
      }
    }
  }

  function formatTimestamp(iso) {
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
      });
    } catch {
      return iso || '—';
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
})();
