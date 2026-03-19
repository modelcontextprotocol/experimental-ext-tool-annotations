"""Structured audit log emitter — zero-infrastructure observability.

Emits JSON lines to stderr (default) for every tool call, recording
SEP-1913 trust annotations alongside timing and status information.
Works with any log aggregator: ELK, Datadog, Splunk, CloudWatch, etc.

Usage:
    from emit import enable_logging

    enable_logging()                                 # JSON to stderr
    enable_logging(stream=sys.stdout)                # JSON to stdout
    enable_logging(callback=send_to_siem)            # custom handler
    enable_logging(agent_id="urn:agent:my-app")      # with agent ID
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Callable, TextIO

from trust_types import TrustAnnotations

# ---------------------------------------------------------------------------
# Module-level emitter state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_emitter: Callable[[dict[str, Any]], None] | None = None
_agent_id: str | None = None


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------

def enable_logging(
    *,
    stream: TextIO | None = None,
    callback: Callable[[dict[str, Any]], None] | None = None,
    agent_id: str | None = None,
    pretty: bool = False,
) -> None:
    """Enable structured audit logging.  Call once at startup.

    Args:
        stream: Output stream (default: stderr).
        callback: Custom handler receiving event dicts.  Overrides stream.
        agent_id: Agent identifier included in every event.
        pretty: Indent JSON for readability (development only).
    """
    global _emitter, _agent_id
    _agent_id = agent_id

    if callback is not None:
        _emitter = callback
    else:
        target = stream or sys.stderr
        indent = 2 if pretty else None

        def _stream_emit(event: dict[str, Any]) -> None:
            line = json.dumps(event, default=str, indent=indent)
            with _lock:
                target.write(line + "\n")
                target.flush()

        _emitter = _stream_emit


def disable_logging() -> None:
    """Disable structured logging."""
    global _emitter, _agent_id
    _emitter = None
    _agent_id = None


# ---------------------------------------------------------------------------
# Internal: emit events
# ---------------------------------------------------------------------------

def _emit_call(tool: str, annotations: TrustAnnotations) -> None:
    """Emit a 'tool.call' event when a tool is invoked."""
    if _emitter is None:
        return
    from annotate import to_wire
    event = {
        "ts": _now_iso(),
        "event": "tool.call",
        "tool": tool,
        "annotations": to_wire(annotations),
    }
    if _agent_id:
        event["agent"] = _agent_id
    _emitter(event)


def _emit_result(
    tool: str,
    annotations: TrustAnnotations,
    duration_ms: float,
    status: str,
    error: str | None = None,
) -> None:
    """Emit a 'tool.result' event when a tool call completes."""
    if _emitter is None:
        return
    from annotate import to_wire
    event: dict[str, Any] = {
        "ts": _now_iso(),
        "event": "tool.result",
        "tool": tool,
        "annotations": to_wire(annotations),
        "duration_ms": round(duration_ms, 2),
        "status": status,
    }
    if error:
        event["error"] = error
    if _agent_id:
        event["agent"] = _agent_id
    _emitter(event)


def _emit_policy(
    tool: str,
    effect: str,
    reason: str,
    **extra: Any,
) -> None:
    """Emit a 'policy.decision' event when a policy rule fires."""
    if _emitter is None:
        return
    event: dict[str, Any] = {
        "ts": _now_iso(),
        "event": "policy.decision",
        "tool": tool,
        "effect": effect,
        "reason": reason,
    }
    event.update(extra)
    if _agent_id:
        event["agent"] = _agent_id
    _emitter(event)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
