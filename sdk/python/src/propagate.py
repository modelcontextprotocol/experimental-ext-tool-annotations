"""Session propagation tracker — implements SEP-1913 propagation rules.

Tracks accumulated annotations across an agent session, applying the
monotonic escalation rules defined in SEP-1913:

  - openWorldHint: boolean union (once true, stays true)
  - maliciousActivityHint: boolean union
  - attribution: set union (accumulates sources)
  - sensitivity: session-max ordering (never decreases)

Usage:
    from propagate import SessionTracker
    from trust_types import ResultAnnotations, SimpleDataClass

    tracker = SessionTracker()

    # After each tool call, merge the result annotations
    tracker.merge(ResultAnnotations(
        sensitivity=SimpleDataClass.PII,
        attribution=("EHR-System",),
    ))

    # Check session state before allowing an outbound call
    if tracker.session.max_sensitivity != SimpleDataClass.NONE:
        print("Session has seen sensitive data — restrict outbound tools")

    # Get session annotations as wire format
    wire = tracker.to_wire()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from trust_types import (
    DataClass,
    Regulated,
    ResultAnnotations,
    RegulatoryScope,
    SessionAnnotations,
    SimpleDataClass,
    max_sensitivity,
    sensitivity_level,
)


class SessionTracker:
    """Tracks accumulated trust annotations across an agent session.

    Thread-safe: all mutations are serialized through a
    ``threading.Lock``.

    The tracker implements the monotonic escalation principle: session
    state can only become MORE restrictive, never less.
    """

    def __init__(
        self,
        session_id: str | None = None,
        allow_reset: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._session = SessionAnnotations()
        self._session_id = session_id
        self._call_count = 0
        self._history: list[_MergeEvent] = []
        self._allow_reset = allow_reset

    @property
    def session(self) -> SessionAnnotations:
        """Read-only snapshot of current session state.

        Returns a defensive copy — mutations on the returned object
        do NOT affect the tracker's internal state.
        """
        with self._lock:
            s = self._session
            return SessionAnnotations(
                open_world_hint=s.open_world_hint,
                malicious_activity_hint=s.malicious_activity_hint,
                attribution=set(s.attribution),
                max_sensitivity=s.max_sensitivity,
            )

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def call_count(self) -> int:
        """Number of tool calls merged into this session."""
        return self._call_count

    # -----------------------------------------------------------------
    # Core: merge tool result into session
    # -----------------------------------------------------------------

    def merge(self, result: ResultAnnotations, tool_name: str = "") -> None:
        """Merge a tool call's result annotations into the session.

        Applies SEP-1913 propagation rules:
          - Boolean union for openWorldHint / maliciousActivityHint
          - Set union for attribution
          - Max-sensitivity for DataClass

        Args:
            result: Annotations from a CallToolResult.
            tool_name: Optional tool name for audit history.
        """
        with self._lock:
            prev_level = sensitivity_level(self._session.max_sensitivity)

            self._session.merge(result)
            self._call_count += 1

            new_level = sensitivity_level(self._session.max_sensitivity)
            escalated = new_level > prev_level

            self._history.append(_MergeEvent(
                tool=tool_name,
                sensitivity=result.sensitivity,
                escalated=escalated,
            ))

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def has_seen_sensitive_data(self) -> bool:
        """Return True if session has seen anything above 'none'."""
        return sensitivity_level(self._session.max_sensitivity) > 0

    def sensitivity_at_least(self, threshold: DataClass) -> bool:
        """Return True if session sensitivity >= the given threshold."""
        return sensitivity_level(self._session.max_sensitivity) >= sensitivity_level(threshold)

    def get_regulatory_scopes(self) -> tuple[str, ...]:
        """Return all regulatory scopes accumulated in the session.

        Returns empty tuple if no regulated data has been seen.
        """
        ms = self._session.max_sensitivity
        if isinstance(ms, Regulated):
            return ms.regulated.scopes
        return ()

    # -----------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------

    def to_wire(self) -> dict[str, Any]:
        """Serialize session state to wire format dict.

        Suitable for including in request annotations when calling
        outbound tools.
        """
        result: dict[str, Any] = {}
        if self._session.open_world_hint:
            result["openWorldHint"] = True
        if self._session.malicious_activity_hint:
            result["maliciousActivityHint"] = True
        if self._session.attribution:
            result["attribution"] = sorted(self._session.attribution)
        if sensitivity_level(self._session.max_sensitivity) > 0:
            from annotate import _sensitivity_to_wire
            result["maxSensitivity"] = _sensitivity_to_wire(
                self._session.max_sensitivity
            )
        return result

    def summary(self) -> str:
        """Human-readable session state summary."""
        lines = [
            f"Session: {self._session_id or '(anonymous)'}",
            f"  Calls: {self._call_count}",
            f"  Open-world: {self._session.open_world_hint}",
            f"  Malicious activity: {self._session.malicious_activity_hint}",
            f"  Max sensitivity: {self._session.max_sensitivity}",
            f"  Attribution: {sorted(self._session.attribution) or '(none)'}",
        ]
        if self._history:
            lines.append("  History:")
            for evt in self._history:
                esc = " [ESCALATED]" if evt.escalated else ""
                lines.append(f"    - {evt.tool or '?'}: {evt.sensitivity}{esc}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset session state.  Violates monotonicity.

        Only available when the tracker was created with
        ``allow_reset=True`` (intended for testing).  Raises
        ``RuntimeError`` otherwise to prevent accidental session
        laundering.
        """
        if not self._allow_reset:
            raise RuntimeError(
                "reset() is disabled by default to preserve monotonic "
                "escalation.  Pass allow_reset=True to the SessionTracker "
                "constructor if you need this (e.g. in tests)."
            )
        with self._lock:
            self._session = SessionAnnotations()
            self._call_count = 0
            self._history.clear()


@dataclass(frozen=True)
class _MergeEvent:
    """Internal audit record of a merge operation."""
    tool: str
    sensitivity: DataClass
    escalated: bool
