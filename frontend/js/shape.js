/* ==========================================================================
   Forensic Lens — shape.js
   Pure functions that translate BACKEND response shapes into the small
   view models the page scripts render. No DOM, no fetch, no state.

   Why this file exists: every page script used to guess at field names
   (data.calls, data.relationships, report.evidence_summary) that the
   backend never sends. All of that guessing now lives here, in one
   place, written against the actual API contract. If the backend
   changes a field, this is the only file that needs editing.

   FORENSIC WORDING: nothing in here adds interpretation. Labels are
   descriptive ("Shared identifier", "Timing"), never conclusions.
   ========================================================================== */

const Shape = (function () {
  const PLACEHOLDER_PARTIES = ['self', 'unknown', '', null, undefined];

  function isRealParty(value) {
    return typeof value === 'string' && !PLACEHOLDER_PARTIES.includes(value.trim().toLowerCase());
  }

  /* ---- Communications ---------------------------------------------- */
  /* Backend: { case_id, total, total_calls, total_messages, records: [Event] }
     Each Event carries category "call" | "message" and a metadata bag. */

  function communications(data) {
    const records = (data && Array.isArray(data.records)) ? data.records : [];

    const calls = records.filter((r) => r.category === 'call').map(toCall);
    const messages = records.filter((r) => r.category === 'message').map(toMessage);

    return {
      caseId: (data && data.case_id) || null,
      total: (data && typeof data.total === 'number') ? data.total : records.length,
      totalCalls: (data && typeof data.total_calls === 'number') ? data.total_calls : calls.length,
      totalMessages: (data && typeof data.total_messages === 'number') ? data.total_messages : messages.length,
      calls,
      messages
    };
  }

  function toCall(event) {
    const meta = event.metadata || {};
    const party = [meta.caller, meta.receiver].find(isRealParty) || 'Unknown party';
    return {
      id: event.id,
      kind: 'call',
      timestamp: event.timestamp,
      direction: meta.direction || 'unknown',
      party,
      caller: meta.caller || 'unknown',
      receiver: meta.receiver || 'unknown',
      duration: typeof meta.duration === 'number' ? meta.duration : null,
      description: event.description || '',
      source: event.source || ''
    };
  }

  function toMessage(event) {
    const meta = event.metadata || {};
    const party = [meta.sender, meta.receiver].find(isRealParty) || 'Unknown party';
    return {
      id: event.id,
      kind: 'message',
      timestamp: event.timestamp,
      direction: meta.direction || 'unknown',
      party,
      sender: meta.sender || 'unknown',
      receiver: meta.receiver || 'unknown',
      content: meta.content || null,
      description: event.description || '',
      source: event.source || ''
    };
  }

  function formatDuration(seconds) {
    if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return '—';
    const total = Math.round(seconds);
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  }

  /* ---- Analysis ------------------------------------------------------ */
  /* Backend: { case_id, total_events, total_correlations,
                correlations: [{correlation_id, related_event_ids, reason,
                                rule, context}],
                summary: {time_window_minutes, correlations_by_rule,
                          events_by_category},
                disclaimer } */

  const RULE_LABELS = {
    time_window: 'Timing',
    shared_identifier: 'Shared identifier',
    location_proximity: 'Location proximity'
  };

  function ruleLabel(rule) {
    return RULE_LABELS[rule] || rule || 'Observed pattern';
  }

  function analysis(data) {
    const correlations = (data && Array.isArray(data.correlations)) ? data.correlations : [];
    const summary = (data && data.summary) || {};

    return {
      caseId: (data && data.case_id) || null,
      totalEvents: (data && data.total_events) || 0,
      totalCorrelations: (data && data.total_correlations) || correlations.length,
      timeWindowMinutes: summary.time_window_minutes ?? null,
      byRule: summary.correlations_by_rule || {},
      byCategory: summary.events_by_category || {},
      disclaimer: (data && data.disclaimer) || '',
      items: correlations.map((c) => ({
        id: c.correlation_id,
        rule: c.rule,
        ruleLabel: ruleLabel(c.rule),
        reason: c.reason || '',
        eventIds: Array.isArray(c.related_event_ids) ? c.related_event_ids : [],
        context: contextPairs(c.context)
      }))
    };
  }

  // Flattens a correlation's context dict into [label, value] pairs for
  // display. Values are reported verbatim — never summarized into a claim.
  function contextPairs(context) {
    if (!context || typeof context !== 'object') return [];
    return Object.entries(context).map(([key, value]) => {
      const label = key.replace(/_/g, ' ').replace(/^./, (ch) => ch.toUpperCase());
      const text = Array.isArray(value) ? value.join(', ') : String(value);
      return [label, text];
    });
  }

  /* ---- Report -------------------------------------------------------- */
  /* Backend sections: disclaimer, case_information, observed_evidence,
     calculated_analysis{timeline_summary, location_summary,
     communication_summary}, potentially_related_events, report_integrity */

  function report(data) {
    const r = data || {};
    const calc = r.calculated_analysis || {};
    const evidence = r.observed_evidence || {};
    const related = r.potentially_related_events || {};

    return {
      disclaimer: r.disclaimer || '',
      caseInformation: pairs(r.case_information),
      evidence: {
        totalItems: evidence.total_items || 0,
        countsByType: evidence.counts_by_evidence_type || {},
        items: Array.isArray(evidence.items) ? evidence.items : []
      },
      timelineSummary: pairs(calc.timeline_summary),
      locationSummary: {
        count: (calc.location_summary && calc.location_summary.location_event_count) || 0,
        points: (calc.location_summary && calc.location_summary.recorded_points) || []
      },
      communicationSummary: pairs(calc.communication_summary),
      related: {
        note: related.note || '',
        count: related.count || 0,
        items: Array.isArray(related.items) ? related.items : []
      },
      integrity: pairs(r.report_integrity)
    };
  }

  // Turns a flat backend object into readable [label, value] pairs.
  function pairs(section) {
    if (!section || typeof section !== 'object') return [];
    return Object.entries(section).map(([key, value]) => {
      const label = key.replace(/_/g, ' ').replace(/^./, (ch) => ch.toUpperCase());
      return [label, readable(value)];
    });
  }

  function readable(value) {
    if (value === null || value === undefined || value === '') return '—';
    if (Array.isArray(value)) return value.length ? value.join(', ') : '—';
    if (typeof value === 'object') {
      const entries = Object.entries(value);
      return entries.length ? entries.map(([k, v]) => `${k}: ${v}`).join(' · ') : '—';
    }
    return String(value);
  }

  /* ---- Evidence upload ----------------------------------------------- */
  /* Backend: { success, case_id, evidence_id, original_filename,
                processing_status, sha256, extracted_files, skipped_files,
                evidence_items, processed_event_count,
                normalization_error_count, device_info, warnings } */

  const UPLOAD_STATUS = {
    processed: { label: 'Processed', className: 'pill-ready' },
    processed_with_warnings: { label: 'Warnings', className: 'pill-parsing' },
    no_supported_evidence: { label: 'No evidence', className: 'pill-queued' }
  };

  function upload(data) {
    const raw = data || {};
    const status = UPLOAD_STATUS[raw.processing_status] ||
      { label: raw.processing_status || 'Uploaded', className: 'pill-queued' };

    return {
      success: raw.success === true,
      evidenceId: raw.evidence_id || null,
      filename: raw.original_filename || '',
      statusLabel: status.label,
      statusClass: status.className,
      sha256: raw.sha256 || null,
      shortHash: raw.sha256 ? raw.sha256.slice(0, 12) : '—',
      extractedFiles: Array.isArray(raw.extracted_files) ? raw.extracted_files : [],
      skippedFiles: Array.isArray(raw.skipped_files) ? raw.skipped_files : [],
      eventCount: raw.processed_event_count || 0,
      errorCount: raw.normalization_error_count || 0,
      deviceInfo: raw.device_info || null,
      warnings: Array.isArray(raw.warnings) ? raw.warnings : []
    };
  }

  /* ---- Dashboard ------------------------------------------------------ */

  function dashboard(timeline, locations, comms, evidence) {
    const events = Array.isArray(timeline) ? timeline : [];
    const points = Array.isArray(locations) ? locations : [];
    const c = communications(comms);

    const timestamps = events
      .map((e) => Date.parse(e.timestamp))
      .filter((t) => Number.isFinite(t));

    return {
      eventCount: events.length,
      locationCount: points.length,
      callCount: c.totalCalls,
      messageCount: c.totalMessages,
      fileCount: (evidence && evidence.total_files) || 0,
      packageCount: (evidence && Array.isArray(evidence.packages)) ? evidence.packages.length : 0,
      errorCount: (evidence && evidence.normalization_error_count) || 0,
      deviceInfo: (evidence && evidence.device_info) || null,
      earliest: timestamps.length ? new Date(Math.min(...timestamps)).toISOString() : null,
      latest: timestamps.length ? new Date(Math.max(...timestamps)).toISOString() : null,
      recent: events.slice(-5).reverse()
    };
  }

  return {
    communications,
    analysis,
    report,
    upload,
    dashboard,
    ruleLabel,
    formatDuration,
    contextPairs
  };
})();

// Allows this file to be unit-tested outside a browser. Harmless in one.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Shape;
}
