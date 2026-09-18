/* ==========================================================================
   Forensic Lens — analysis.js
   NOT YET WIRED TO A PAGE. analysis.html hasn't been built yet, so this
   exposes a ready-to-use loader for whenever that page is built.

   IMPORTANT (per project rules): this file only ever displays what the
   backend returns. It must never phrase a correlation as a conclusion
   ("proves", "guilty", "committed") — that judgment stays out of the
   frontend entirely. renderAnalysisSummary() below is intentionally
   neutral/descriptive for that reason.
   ========================================================================== */

function loadAnalysis(caseId, { onData, onEmpty, onError } = {}) {
  return Api.getAnalysis(caseId)
    .then((data) => {
      const relationships = (data && data.relationships) || [];
      if (!relationships.length) {
        if (onEmpty) onEmpty();
        return;
      }
      if (onData) onData(relationships);
    })
    .catch((err) => {
      console.error('analysis.js: failed to load analysis', err);
      if (onError) onError(err);
    });
}

// Renders one relationship as neutral, descriptive text — never a
// judgment. Intended for a future analysis.html to call per item.
function renderAnalysisSummary(relationship) {
  const parts = [];
  if (relationship.description) parts.push(relationship.description);
  if (relationship.shared_identifier) parts.push(`Shared identifier: ${relationship.shared_identifier}`);
  if (relationship.time_relationship) parts.push(`Timing: ${relationship.time_relationship}`);
  if (relationship.location_relationship) parts.push(`Location: ${relationship.location_relationship}`);
  return parts.join(' — ') || 'Relationship observed between events.';
}
