/* ==========================================================================
   Forensic Lens — communications.js
   Renders the call and message records for the active case on
   communications.html.

   Fixed in this integration pass: this file read data.calls /
   data.messages, which the backend never sends. The real response is
   { case_id, total, total_calls, total_messages, records: [Event] }
   where each Event has category "call" | "message" and a metadata bag.
   That translation now lives in Shape.communications().
   ========================================================================== */

(function () {
  const loadingState = document.querySelector('#comms-loading');
  const emptyState = document.querySelector('#comms-empty');
  const errorState = document.querySelector('#comms-error');
  const populated = document.querySelector('#comms-populated');
  if (!loadingState && !emptyState && !populated) return; // not this page

  const states = [loadingState, emptyState, errorState, populated];
  const caseId = CaseState.getCurrentCaseId();

  if (!caseId) {
    UI.showOnly(states, emptyState);
    return;
  }

  UI.showOnly(states, loadingState);

  Api.getCommunications(caseId)
    .then((raw) => {
      const data = Shape.communications(raw);
      if (!data.total) {
        UI.showOnly(states, emptyState);
        return;
      }
      UI.showOnly(states, populated);
      UI.setText('#comms-count-calls', String(data.totalCalls));
      UI.setText('#comms-count-messages', String(data.totalMessages));
      renderCalls(data.calls);
      renderMessages(data.messages);
    })
    .catch((err) => {
      console.error('communications.js: failed to load communications', err);
      UI.showOnly(states, errorState, err.message);
    });

  function renderCalls(calls) {
    const body = document.querySelector('#calls-table-body');
    if (!body) return;
    if (!calls.length) {
      body.innerHTML = '<tr><td colspan="4"><div class="empty-note">No call records</div></td></tr>';
      return;
    }
    body.innerHTML = calls.map((call) => `
      <tr>
        <td class="mono">${UI.escapeHtml(UI.formatTimestamp(call.timestamp))}</td>
        <td class="mono">${UI.escapeHtml(call.party)}</td>
        <td>${UI.escapeHtml(call.direction)}</td>
        <td class="mono">${UI.escapeHtml(Shape.formatDuration(call.duration))}</td>
      </tr>
    `).join('');
  }

  function renderMessages(messages) {
    const body = document.querySelector('#messages-table-body');
    if (!body) return;
    if (!messages.length) {
      body.innerHTML = '<tr><td colspan="4"><div class="empty-note">No message records</div></td></tr>';
      return;
    }
    body.innerHTML = messages.map((msg) => `
      <tr>
        <td class="mono">${UI.escapeHtml(UI.formatTimestamp(msg.timestamp))}</td>
        <td class="mono">${UI.escapeHtml(msg.party)}</td>
        <td>${UI.escapeHtml(msg.direction)}</td>
        <td>${UI.escapeHtml(msg.content || '—')}</td>
      </tr>
    `).join('');
  }
})();
