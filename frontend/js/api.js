/* ==========================================================================
   Forensic Lens — api.js
   The ONLY file in this project that communicates with the backend.
   No other .js file may contain fetch(), XMLHttpRequest, axios, a direct
   API URL, or any HTTP request logic — everything goes through Api.* below.

   Also owns the lightweight "which case is active" state (CaseState),
   since every endpoint in the contract is scoped to a case id and that
   state doesn't need anything heavier than localStorage + a query param.
   ========================================================================== */

// Change this one line when the backend moves (local dev, staging, etc).
// Nothing else in the project should ever hard-code a backend URL.
const API_BASE_URL = "http://127.0.0.1:8000";

/* ---------------------------------------------------------------------- */
/* Active case id                                                          */
/* ---------------------------------------------------------------------- */

const CaseState = (function () {
  const KEY = "flCurrentCaseId";

  function getCurrentCaseId() {
    const fromUrl = new URLSearchParams(window.location.search).get("case_id");
    if (fromUrl) {
      localStorage.setItem(KEY, fromUrl);
      return fromUrl;
    }
    return localStorage.getItem(KEY);
  }

  function setCurrentCaseId(caseId) {
    localStorage.setItem(KEY, caseId);
  }

  function clearCurrentCaseId() {
    localStorage.removeItem(KEY);
  }

  return { getCurrentCaseId, setCurrentCaseId, clearCurrentCaseId };
})();

/* ---------------------------------------------------------------------- */
/* Error type — page JS can check err.status / err.message                 */
/* ---------------------------------------------------------------------- */

class ApiError extends Error {
  constructor(message, { status = null, cause = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.cause = cause;
  }
}

/* ---------------------------------------------------------------------- */
/* Core request helper                                                     */
/* ---------------------------------------------------------------------- */

function httpStatusMessage(status) {
  switch (status) {
    case 400: return "The request was invalid.";
    case 404: return "That wasn't found.";
    case 422: return "The backend couldn't process that data.";
    case 500: return "The backend hit an internal error.";
    default: return `Request failed (HTTP ${status}).`;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch (cause) {
    // Network failure / backend not running / CORS rejection at the
    // network layer all land here. We don't try to work around CORS —
    // that's the backend's job to configure.
    throw new ApiError("Couldn't reach the backend. Is it running?", { cause });
  }

  if (response.status === 204) return null;

  const text = await response.text();
  let payload = null;

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (cause) {
      throw new ApiError(
        response.ok
          ? "Backend returned a response that wasn't valid JSON."
          : `Backend returned an unreadable error (HTTP ${response.status}).`,
        { status: response.status, cause }
      );
    }
  }

  if (!response.ok) {
    const detail = payload && (payload.detail || payload.message);
    throw new ApiError(detail || httpStatusMessage(response.status), { status: response.status });
  }

  return payload;
}

/* ---------------------------------------------------------------------- */
/* Endpoints — one function per backend contract entry, nothing invented   */
/* ---------------------------------------------------------------------- */

const Api = (function () {
  function createCase(name, description) {
    return request("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description })
    });
  }

  function getCases() {
    return request("/cases");
  }

  function getCase(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}`);
  }

  function uploadEvidence(caseId, file) {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/cases/${encodeURIComponent(caseId)}/evidence`, {
      method: "POST",
      body: formData
      // No Content-Type header here on purpose — the browser sets the
      // correct multipart boundary automatically for FormData.
    });
  }

  function getTimeline(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/timeline`);
  }

  function getLocations(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/locations`);
  }

  function getCommunications(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/communications`);
  }

  function getAnalysis(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/analysis`);
  }

  function getReport(caseId) {
    return request(`/cases/${encodeURIComponent(caseId)}/report`);
  }

  return {
    createCase,
    getCases,
    getCase,
    uploadEvidence,
    getTimeline,
    getLocations,
    getCommunications,
    getAnalysis,
    getReport
  };
})();
