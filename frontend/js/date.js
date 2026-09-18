/* ==========================================================================
   Forensic Lens — date.js
   Not part of the original file set — this is a fix of the version that
   was uploaded for review. Two bugs corrected below; nothing else changed.
   This file is still standalone: it isn't included in any page's <script>
   tags yet, and its data source (a purely local timestamp) doesn't reflect
   anything the backend actually reports. If the intent is "when was this
   case last processed," that should come from the backend (e.g. a
   processed_at field on the evidence-upload or case response) via api.js
   instead of a client-side clock — flagging that rather than guessing.

   Bugs fixed from the uploaded version:
   1. Read key was "analysisTimeStamp" but the write key was
      "analysisTimestamp" (different casing) — the read would always
      miss, so it "re-detected" as first run on every page load.
      Both now use "analysisTimestamp".
   2. getElementById("date-time display") — ids can't contain spaces;
      this would never match a real element. Changed to
      "date-time-display". Add an element with that id to use this file:
      <span id="date-time-display"></span>
   ========================================================================== */

(function () {
  const KEY = 'analysisTimestamp';
  const targetEl = document.getElementById('date-time-display');
  if (!targetEl) return; // nothing to write to on this page

  let savedTime = localStorage.getItem(KEY);
  if (!savedTime) {
    savedTime = new Date().toLocaleString('en-IN', {
      eday: 'numeric',
      month: 'short',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  }
  targetEl.textContent = 'Last done ' + savedTime;
  const currentTime = new Date().toLocaleString('en-IN', {
    day: 'numeric',
      month: 'short',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
  });
    localStorage.setItem(KEY, currentTime);
})();
