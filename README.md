# Mobile Device Forensic Analysis System

A hackathon prototype for analysing **simulated** mobile-device forensic evidence.
An investigator creates a case, uploads a simulated evidence `.zip`, and the system
extracts it, parses it into a single Unified Event structure, and exposes the
timeline, locations, communications, deterministic correlations and a structured
report through a FastAPI backend that the browser frontend consumes.

All evidence is simulated. The system reports **observed evidence**, **calculated
analysis** and **potentially related events** — never conclusions about conduct,
identity or intent.

---

## Layout

```
backend/     FastAPI application (no database — state lives in app/state.py)
frontend/    Static HTML/CSS/JS client (no build step, no framework)
```

## Running it

Two processes: the API, and a static file server for the frontend.

**1. Backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is then on `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`.

**2. Frontend**

Serve it over HTTP rather than opening the files directly — browsers treat a
`file://` page as an opaque origin, which makes cross-origin requests unreliable.

```bash
cd frontend
python -m http.server 5500
```

Then open `http://127.0.0.1:5500/index.html`.

The backend's development CORS is open by default. To narrow it:

```bash
CORS_ORIGINS="http://127.0.0.1:5500" uvicorn app.main:app --reload
```

If the backend ever moves, change the one line at the top of `frontend/js/api.js`,
or set `window.FORENSIC_API_BASE_URL` before that script loads.

## Using it

1. **Cases** — create a case, or open an existing one. The case you open is the
   case every other page works against.
2. **Evidence** — drop a simulated evidence `.zip`. The backend saves it, records
   its SHA-256, extracts the supported files, and parses them.
3. **Dashboard / Timeline / Location / Communications** — review what was recorded.
4. **Analysis** — deterministic correlations flagged for human review.
5. **Report** — the structured forensic report, printable via the export button.

A supported evidence archive may contain any of: `device.json`, `app_activity.json`,
`calls.json`, `messages.json`, `locations.json`, `system_logs.json`. Anything else in
the archive is skipped.

## Testing

```bash
cd backend
python tests/test_full_integration.py     # starts its own backend process
# or: pytest tests/test_full_integration.py -v
```

## Notes

- There is **no database**. Cases, evidence and events live in memory for as long as
  the backend process runs; restarting it clears them. Uploaded archives remain on
  disk under `backend/uploads`.
- Uploaded archives are treated strictly as data — nothing in them is executed. The
  extraction service enforces path-traversal and zip-bomb protections.
