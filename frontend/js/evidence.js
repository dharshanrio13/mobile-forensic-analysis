/* ==========================================================================
   Forensic Lens — evidence.js
   Wires the dropzone/browse UI to a real upload through api.js. Drag/drop
   and file-picker DOM logic is unchanged from before; what changed is
   that selecting a file now calls Api.uploadEvidence() instead of just
   inserting a row.

   The evidence-upload response shape isn't finalized on the backend yet
   (see integration notes), so normalizeEvidenceResponse() below is an
   isolated adapter — update ONLY that function when the real fields are
   confirmed, rather than the event-handling code around it.
   ========================================================================== */

(function () {
  const dropzone = document.querySelector('#dropzone');
  const browseBtn = document.querySelector('[data-action="browse"]');
  const fileInput = document.querySelector('#evidence-file-input');
  const tableBody = document.querySelector('#file-table-body');
  const emptyRow = document.querySelector('#file-table-empty');
  const caseIdInput = document.querySelector('#case-id-input');
  const caseIdSetBtn = document.querySelector('#case-id-set-btn');

  // There's no case-creation/picker page yet, so this is the one place a
  // case id can be set manually. Prefill from whatever's already active.
  if (caseIdInput) {
    const existing = CaseState.getCurrentCaseId();
    if (existing) caseIdInput.value = existing;
  }
  if (caseIdSetBtn && caseIdInput) {
    caseIdSetBtn.addEventListener('click', () => {
      const value = caseIdInput.value.trim();
      if (!value) return;
      CaseState.setCurrentCaseId(value);
      location.reload(); // refresh so the sidebar/topbar (cases.js) picks it up
    });
  }

  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });
  });
  ['dragleave', 'drop'].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
    });
  });
  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer ? e.dataTransfer.files : [];
    if (files && files.length) handleFile(files[0]);
  });

  if (browseBtn && fileInput) {
    browseBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) handleFile(fileInput.files[0]);
    });
  }

  function handleFile(file) {
    const caseId = CaseState.getCurrentCaseId();
    if (!caseId) {
      showRowError(file, 'No active case selected');
      return;
    }

    if (emptyRow) emptyRow.style.display = 'none';

    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="name mono">${escapeHtml(file.name)}</td>
      <td>${(file.size / (1024 * 1024)).toFixed(1)} MB</td>
      <td><span class="pill pill-queued" data-status-pill>Uploading</span></td>
      <td>Just now</td>
    `;
    tableBody.prepend(row);
    const pill = row.querySelector('[data-status-pill]');

    Api.uploadEvidence(caseId, file)
      .then((raw) => {
        const evidence = normalizeEvidenceResponse(raw);
        pill.textContent = evidence.statusLabel;
        pill.className = 'pill ' + evidence.statusClass;
      })
      .catch((err) => {
        console.error('evidence.js: upload failed', err);
        pill.textContent = 'Failed';
        pill.className = 'pill pill-queued';
        pill.title = err.message || 'Upload failed';
      });
  }

  function showRowError(file, message) {
    if (emptyRow) emptyRow.style.display = 'none';
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="name mono">${escapeHtml(file.name)}</td>
      <td>—</td>
      <td><span class="pill pill-queued">Failed</span></td>
      <td>${escapeHtml(message)}</td>
    `;
    tableBody.prepend(row);
  }

  // ---- Isolated adapter -------------------------------------------------
  // The backend evidence-upload response isn't finalized. This function
  // is the ONLY place that reads its fields, so it's the only place that
  // needs to change once the contract is confirmed. It defensively checks
  // a few likely field names rather than assuming one.
  function normalizeEvidenceResponse(raw) {
    const status = (raw && (raw.status || raw.processing_status || '')).toLowerCase();
    if (status.includes('ready') || status.includes('complete') || status.includes('done')) {
      return { statusLabel: 'Ready', statusClass: 'pill-ready' };
    }
    if (status.includes('pars') || status.includes('process')) {
      return { statusLabel: 'Parsing', statusClass: 'pill-parsing' };
    }
    if (status.includes('queue')) {
      return { statusLabel: 'Queued', statusClass: 'pill-queued' };
    }
    // Unknown/unspecified status from the backend — show the raw value
    // rather than guessing, so it's obvious this needs the adapter updated.
    return { statusLabel: status ? raw.status : 'Uploaded', statusClass: 'pill-queued' };
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
})();
