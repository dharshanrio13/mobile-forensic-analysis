/* ==========================================================================
   Forensic Lens — evidence.js
   Wires the dropzone/browse UI to a real upload through api.js, and
   loads the evidence already registered for this case so the table
   isn't empty after a page reload.

   Fixed in this integration pass: the old normalizeEvidenceResponse()
   guessed at field names and mapped the backend's real
   processing_status of "processed" to a "Parsing" pill (because the
   string contains "process"). Status mapping now lives in
   Shape.upload(), written against the actual contract:
   processed | processed_with_warnings | no_supported_evidence.

   The manual case-id box is gone — cases.html is a real picker now.
   ========================================================================== */

(function () {
  const dropzone = document.querySelector('#dropzone');
  const browseBtn = document.querySelector('[data-action="browse"]');
  const fileInput = document.querySelector('#evidence-file-input');
  const tableBody = document.querySelector('#file-table-body');
  const emptyRow = document.querySelector('#file-table-empty');
  const detailPanel = document.querySelector('#upload-detail');

  if (!dropzone) return;

  const caseId = CaseState.getCurrentCaseId();

  loadExistingEvidence();

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

  // ---- Already-registered evidence ------------------------------------
  function loadExistingEvidence() {
    if (!caseId) return;
    Api.getEvidence(caseId)
      .then((data) => {
        if (!data || !data.total_files) return;
        if (emptyRow) emptyRow.style.display = 'none';
        data.files.forEach((file) => {
          const pkg = data.packages[0] || {};
          addRow({
            name: file.filename,
            size: '—',
            statusLabel: 'Registered',
            statusClass: 'pill-ready',
            added: UI.formatTimestamp(file.uploaded_at),
            hash: pkg.sha256 ? pkg.sha256.slice(0, 12) : '—'
          });
        });
      })
      .catch((err) => console.error('evidence.js: could not load existing evidence', err));
  }

  // ---- Upload ----------------------------------------------------------
  function handleFile(file) {
    if (!caseId) {
      addRow({ name: file.name, size: '—', statusLabel: 'No case', statusClass: 'pill-queued', added: 'Select a case first', hash: '—' });
      return;
    }

    if (emptyRow) emptyRow.style.display = 'none';

    const row = addRow({
      name: file.name,
      size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
      statusLabel: 'Uploading',
      statusClass: 'pill-queued',
      added: 'Just now',
      hash: '—'
    });
    const pill = row.querySelector('[data-status-pill]');
    const hashCell = row.querySelector('[data-hash-cell]');

    Api.uploadEvidence(caseId, file)
      .then((raw) => {
        const result = Shape.upload(raw);
        pill.textContent = result.statusLabel;
        pill.className = 'pill ' + result.statusClass;
        hashCell.textContent = result.shortHash;
        hashCell.title = result.sha256 || '';
        renderDetail(result);
      })
      .catch((err) => {
        console.error('evidence.js: upload failed', err);
        pill.textContent = 'Failed';
        pill.className = 'pill pill-queued';
        pill.title = err.message || 'Upload failed';
        renderError(err);
      });
  }

  function addRow({ name, size, statusLabel, statusClass, added, hash }) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="name mono">${UI.escapeHtml(name)}</td>
      <td>${UI.escapeHtml(size)}</td>
      <td><span class="pill ${UI.escapeHtml(statusClass)}" data-status-pill>${UI.escapeHtml(statusLabel)}</span></td>
      <td class="mono" data-hash-cell>${UI.escapeHtml(hash)}</td>
      <td>${UI.escapeHtml(added)}</td>
    `;
    tableBody.prepend(row);
    return row;
  }

  // Shows what the backend actually reported about the package: the
  // digest it recorded, which files it extracted, which it skipped, how
  // many events were produced, and anything that failed to parse.
  function renderDetail(result) {
    if (!detailPanel) return;
    const skipped = result.skippedFiles
      .map((s) => `${s.entry} (${s.reason})`)
      .join(', ') || 'None';
    const warnings = result.warnings.length
      ? `<li><strong>Warnings:</strong> ${UI.escapeHtml(result.warnings.join(' · '))}</li>`
      : '';
    const device = result.deviceInfo
      ? `<li><strong>Device:</strong> ${UI.escapeHtml(Object.entries(result.deviceInfo).map(([k, v]) => `${k}: ${v}`).join(' · '))}</li>`
      : '';

    detailPanel.innerHTML = `
      <ul class="report-summary-list">
        <li><strong>Status:</strong> ${UI.escapeHtml(result.statusLabel)}</li>
        <li><strong>SHA-256:</strong> <span class="mono" style="word-break:break-all;">${UI.escapeHtml(result.sha256 || '—')}</span></li>
        <li><strong>Extracted:</strong> ${UI.escapeHtml(result.extractedFiles.join(', ') || 'None')}</li>
        <li><strong>Skipped:</strong> ${UI.escapeHtml(skipped)}</li>
        <li><strong>Events produced:</strong> ${UI.escapeHtml(result.eventCount)}</li>
        <li><strong>Records that failed to parse:</strong> ${UI.escapeHtml(result.errorCount)}</li>
        ${device}
        ${warnings}
      </ul>
    `;
  }

  function renderError(err) {
    if (!detailPanel) return;
    detailPanel.innerHTML = `<div class="empty-note">Upload rejected: ${UI.escapeHtml(err.message || 'Unknown error')}</div>`;
  }
})();
