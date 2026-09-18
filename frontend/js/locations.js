/* ==========================================================================
   Forensic Lens — locations.js
   Fetches location events via Api.getLocations(), validates coordinates,
   and renders them on a real Leaflet map: one marker per point, joined by
   a polyline in chronological order, plus a fullscreen toggle on the map
   panel for closer inspection. List <-> marker selection is two-way.

   Leaflet + OpenStreetMap tiles are loaded from cdnjs in locations.html —
   this file only assumes a global `L` is available.
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#location-loading');
  const emptyState = document.querySelector('#location-empty');
  const errorState = document.querySelector('#location-error');
  const layout = document.querySelector('#location-layout');
  const listEl = document.querySelector('#location-list');
  const mapFrame = document.querySelector('#map-frame');
  const mapEl = document.querySelector('#leaflet-map');
  const fullscreenBtn = document.querySelector('#map-fullscreen-btn');

  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    show(emptyState);
    return;
  }

  show(loadingState);

  Api.getLocations(caseId)
    .then((raw) => {
      const points = (raw || []).filter(hasUsableCoordinates);
      if (!points.length) {
        show(emptyState);
        return;
      }
      show(layout);
      render(sortByTime(points));
    })
    .catch((err) => {
      console.error('locations.js: failed to load locations', err);
      show(errorState, err.message);
    });

  function hasUsableCoordinates(point) {
    return typeof point.latitude === 'number' &&
           typeof point.longitude === 'number' &&
           Number.isFinite(point.latitude) &&
           Number.isFinite(point.longitude);
  }

  function sortByTime(points) {
    return [...points].sort((a, b) => {
      const ta = Date.parse(a.timestamp) || 0;
      const tb = Date.parse(b.timestamp) || 0;
      return ta - tb;
    });
  }

  function render(points) {
    // ---- List (a sidebar of points next to the map) --------------------
    listEl.innerHTML = '';
    points.forEach((p, i) => {
      const row = document.createElement('div');
      row.className = 'loc-row' + (i === points.length - 1 ? ' active' : '');
      row.dataset.point = 'p' + i;
      row.innerHTML = `
        <div class="lt mono">${escapeHtml(formatTimestamp(p.timestamp))}</div>
        <div class="lc mono">${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}${p.source ? ' · ' + escapeHtml(p.source) : ''}</div>
      `;
      listEl.appendChild(row);
    });

    // ---- Real map --------------------------------------------------------
    const map = L.map(mapEl, { zoomControl: true }).setView([points[0].latitude, points[0].longitude], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const latLngs = points.map((p) => [p.latitude, p.longitude]);

    // Line connecting points in time order.
    L.polyline(latLngs, { color: '#4A9BB5', weight: 3, opacity: 0.85, dashArray: '6 6' }).addTo(map);

    const markers = points.map((p, i) => {
      const isFirst = i === 0;
      const isLast = i === points.length - 1;
      const marker = L.circleMarker([p.latitude, p.longitude], {
        radius: isFirst || isLast ? 8 : 6,
        color: isLast ? '#6DBBD4' : (isFirst ? '#8B96A3' : '#4A9BB5'),
        weight: 2,
        fillColor: isLast || isFirst ? '#0B0F14' : '#4A9BB5',
        fillOpacity: 1
      }).addTo(map);

      marker.bindPopup(
        `<strong>${escapeHtml(formatTimestamp(p.timestamp))}</strong><br>` +
        `${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}` +
        (p.source ? `<br>${escapeHtml(p.source)}` : '')
      );

      marker.on('click', () => selectPoint('p' + i));
      return marker;
    });

    map.fitBounds(L.latLngBounds(latLngs), { padding: [30, 30] });

    // ---- Two-way selection: list row <-> marker ---------------------------
    const rows = document.querySelectorAll('.loc-row[data-point]');
    rows.forEach((row) => {
      row.addEventListener('click', () => {
        selectPoint(row.dataset.point);
        const idx = parseInt(row.dataset.point.slice(1), 10);
        map.panTo(latLngs[idx]);
        markers[idx].openPopup();
      });
    });

    function selectPoint(id) {
      rows.forEach((r) => r.classList.toggle('active', r.dataset.point === id));
    }

    // ---- Fullscreen toggle --------------------------------------------
    if (fullscreenBtn && mapFrame) {
      fullscreenBtn.addEventListener('click', () => {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else if (mapFrame.requestFullscreen) {
          mapFrame.requestFullscreen();
        }
      });
      document.addEventListener('fullscreenchange', () => {
        // Leaflet needs to recalculate its size after the container
        // itself resizes, or the map renders at the old dimensions.
        setTimeout(() => map.invalidateSize(), 100);
      });
    }
  }

  function show(el, message) {
    [loadingState, emptyState, errorState, layout].forEach((s) => {
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
