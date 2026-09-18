/* ==========================================================================
   Forensic Lens — communications.js
   NOT YET WIRED TO A PAGE. communications.html (calls/messages tables per
   the original structure.txt) hasn't been built yet, so this file exposes
   a ready-to-use loader that a future page can call, rather than
   guessing at markup that doesn't exist.

   dashboard.js already calls Api.getCommunications() directly for its
   summary counts — this file is for a dedicated communications view.
   ========================================================================== */

function loadCommunications(caseId, { onData, onEmpty, onError } = {}) {
  return Api.getCommunications(caseId)
    .then((data) => {
      const calls = (data && data.calls) || [];
      const messages = (data && data.messages) || [];
      if (!calls.length && !messages.length) {
        if (onEmpty) onEmpty();
        return;
      }
      if (onData) onData({ calls, messages });
    })
    .catch((err) => {
      console.error('communications.js: failed to load communications', err);
      if (onError) onError(err);
    });
}
