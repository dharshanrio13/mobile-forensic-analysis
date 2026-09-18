"""
Centralized in-memory application state.

There is NO database in this project. This module is the single
source of truth for everything the running server knows about:
cases, the evidence registered against them, the Unified Events
normalized out of that evidence, and any records that failed to
normalize.

Everything here lives in this process's memory only. Restarting the
server clears all of it - that is an accepted trade-off for this
hackathon prototype. Original uploaded ZIPs remain on disk under
settings.UPLOAD_DIR, and extracted files under settings.TEMP_DIR,
but the *processed* state (cases/evidence/events) is memory-only.

Design rules this module exists to enforce:
    - ONE store, imported by every route and service that needs it
      (`from app.state import app_state`), rather than a separate
      global dict scattered through each route file.
    - No ORM, no sessions, no query language - just Python objects.
    - Access is guarded by a lock, because FastAPI runs synchronous
      endpoint functions in a thread pool, so two requests really can
      touch this store at the same time.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.case import Case
from app.models.event import Event
from app.models.evidence import Evidence


@dataclass
class CaseState:
    """
    Everything the application currently knows about one case.

    Attributes:
        case: The Case itself.
        evidence_items: Evidence records registered for this case (one
            per supported evidence file successfully extracted from an
            uploaded package).
        events: Unified Events normalized from that evidence. This is
            what the timeline, locations, communications, analysis and
            report endpoints all read from.
        normalization_errors: Source records that could not be parsed
            into Events, kept for completeness reporting.
        device_info: Contents of a device.json, if the uploaded
            package contained one. There is no parser for device.json
            (it describes the device rather than a timestamped
            occurrence), so it is stored as-is rather than turned into
            events.
        integrity_records: One entry per uploaded package recording its
            original filename and SHA-256 digest.
        warnings: Non-fatal issues noticed while processing uploads.
    """

    case: Case
    evidence_items: List[Evidence] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    normalization_errors: List[Dict[str, Any]] = field(default_factory=list)
    device_info: Optional[Dict[str, Any]] = None
    integrity_records: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ApplicationState:
    """
    The one in-memory store used by the whole application.

    Import the module-level `app_state` instance rather than creating
    your own - a second instance would be a second source of truth,
    which is exactly what this module exists to prevent.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._case_states: Dict[str, CaseState] = {}

    # ---------------------------------------------------------------
    # Cases
    # ---------------------------------------------------------------

    def create_case(self, name: str, description: str) -> Case:
        """Create a new Case and register empty state for it."""
        case = Case(name=name, description=description)
        with self._lock:
            self._case_states[case.id] = CaseState(case=case)
        return case

    def list_cases(self) -> List[Case]:
        """Every case currently held, in creation order."""
        with self._lock:
            return [state.case for state in self._case_states.values()]

    def get_case(self, case_id: str) -> Optional[Case]:
        """Return one Case, or None if no case with that id exists."""
        with self._lock:
            state = self._case_states.get(case_id)
            return state.case if state else None

    def case_exists(self, case_id: str) -> bool:
        with self._lock:
            return case_id in self._case_states

    def get_case_state(self, case_id: str) -> Optional[CaseState]:
        """
        Return the full CaseState (case + evidence + events + errors),
        or None if the case doesn't exist.
        """
        with self._lock:
            return self._case_states.get(case_id)

    # ---------------------------------------------------------------
    # Processed evidence
    # ---------------------------------------------------------------

    def record_processed_evidence(
        self,
        case_id: str,
        evidence_items: List[Evidence],
        events: List[Event],
        normalization_errors: List[Dict[str, Any]],
        integrity_record: Optional[Dict[str, Any]] = None,
        device_info: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        """
        Append the results of one processed evidence package to a
        case's state.

        Uploading a second package for the same case adds to what is
        already there rather than replacing it.

        Raises:
            KeyError: If `case_id` doesn't exist. Callers should have
                already validated the case (routes do this and return
                a 404), so reaching this is a programming error.
        """
        with self._lock:
            state = self._case_states.get(case_id)
            if state is None:
                raise KeyError(f"Unknown case_id: {case_id}")

            state.evidence_items.extend(evidence_items)
            state.events.extend(events)
            state.normalization_errors.extend(normalization_errors)

            if integrity_record:
                state.integrity_records.append(integrity_record)
            if device_info is not None:
                state.device_info = device_info
            if warnings:
                state.warnings.extend(warnings)

    # ---------------------------------------------------------------
    # Read helpers used by the analysis/reporting routes
    # ---------------------------------------------------------------

    def get_events(self, case_id: str) -> List[Event]:
        """
        Every normalized Event for a case, in ingestion order, or an
        empty list if the case has no events yet.

        Returns a copy so callers can sort/filter freely without
        mutating stored state.
        """
        with self._lock:
            state = self._case_states.get(case_id)
            return list(state.events) if state else []

    def get_evidence_items(self, case_id: str) -> List[Evidence]:
        with self._lock:
            state = self._case_states.get(case_id)
            return list(state.evidence_items) if state else []

    def get_integrity_records(self, case_id: str) -> List[Dict[str, Any]]:
        """One record per uploaded package: its filename and SHA-256 digest."""
        with self._lock:
            state = self._case_states.get(case_id)
            return list(state.integrity_records) if state else []

    def get_device_info(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self._case_states.get(case_id)
            return state.device_info if state else None

    def get_normalization_errors(self, case_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            state = self._case_states.get(case_id)
            return list(state.normalization_errors) if state else []

    def reset(self) -> None:
        """
        Drop all state. Intended for tests that want a clean slate
        without restarting the process.
        """
        with self._lock:
            self._case_states.clear()


# The single shared store. Import this, don't instantiate your own.
app_state = ApplicationState()
