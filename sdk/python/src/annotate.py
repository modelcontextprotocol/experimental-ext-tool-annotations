"""Declarative trust annotation decorator and wire-format serialization.

Attach SEP-1913 trust annotations to any function with a single decorator.
Read them back at runtime for policy evaluation, logging, and MCP wire output.

Usage:
    from trust_annotated, get_trust_annotations, to_wire
    from ReturnMetadata, Source, Regulated

    @trust_annotated(
        return_metadata=ReturnMetadata(
            source=Source.INTERNAL,
            sensitivity=Regulated.of("HIPAA"),
        ),
        attribution=("EHR-System",),
    )
    async def patient_lookup(pid: str) -> dict:
        ...

    # Read metadata
    ann = get_trust_annotations(patient_lookup)
    assert ann.return_metadata.source == Source.INTERNAL

    # Serialize to MCP wire format
    wire = to_wire(ann)
    # → {"attribution": ["EHR-System"], "returnMetadata": {"source": "internal", ...}}
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar

from trust_types import (
    DataClass,
    Destination,
    InputMetadata,
    Outcome,
    Regulated,
    ReturnMetadata,
    SimpleDataClass,
    Source,
    TrustAnnotations,
)

_TRUST_ATTR = "__mcp_trust_annotations__"
F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def trust_annotated(
    *,
    malicious_activity_hint: bool | None = None,
    attribution: tuple[str, ...] = (),
    input_metadata: InputMetadata | None = None,
    return_metadata: ReturnMetadata | None = None,
) -> Callable[[F], F]:
    """Attach SEP-1913 trust annotations to a tool function.

    This is a pure metadata decorator — it does NOT wrap the function
    at runtime unless logging is enabled (see emit.py).  When logging
    is disabled, overhead is effectively zero.

    Args:
        malicious_activity_hint: Tool may encounter malicious content.
        attribution: Source identifiers for the data this tool handles.
        input_metadata: Where inputs go and their security implications.
        return_metadata: Where outputs come from and their sensitivity.

    Returns:
        Decorator that attaches TrustAnnotations to the function.
    """
    annotations = TrustAnnotations(
        malicious_activity_hint=malicious_activity_hint,
        attribution=attribution,
        input_metadata=input_metadata,
        return_metadata=return_metadata,
    )

    def decorator(fn: F) -> F:
        setattr(fn, _TRUST_ATTR, annotations)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from emit import _emit_call, _emit_result
            _emit_call(fn.__name__, annotations)
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.monotonic() - start) * 1000
                _emit_result(fn.__name__, annotations, elapsed, "ok")
                return result
            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                _emit_result(fn.__name__, annotations, elapsed, "error", str(exc))
                raise

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from emit import _emit_call, _emit_result
            _emit_call(fn.__name__, annotations)
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                elapsed = (time.monotonic() - start) * 1000
                _emit_result(fn.__name__, annotations, elapsed, "ok")
                return result
            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                _emit_result(fn.__name__, annotations, elapsed, "error", str(exc))
                raise

        wrapper = async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
        setattr(wrapper, _TRUST_ATTR, annotations)
        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Runtime inspection
# ---------------------------------------------------------------------------

def get_trust_annotations(fn: Callable[..., Any]) -> TrustAnnotations | None:
    """Read trust annotations from a decorated function.

    Returns None if the function is not annotated.
    """
    return getattr(fn, _TRUST_ATTR, None)


def is_trust_annotated(fn: Callable[..., Any]) -> bool:
    """Check whether a function has trust annotations."""
    return hasattr(fn, _TRUST_ATTR)


# ---------------------------------------------------------------------------
# Wire-format serialization (Python → MCP JSON)
# ---------------------------------------------------------------------------

def to_wire(annotations: TrustAnnotations) -> dict[str, Any]:
    """Serialize TrustAnnotations to MCP wire format dict.

    Output can be spread into ToolAnnotations in a tools/list response:

        tool = {
            "name": "patient_lookup",
            "description": "...",
            "annotations": {
                "readOnlyHint": True,
                **to_wire(trust_annotations),
            }
        }
    """
    result: dict[str, Any] = {}

    if annotations.malicious_activity_hint is not None:
        result["maliciousActivityHint"] = annotations.malicious_activity_hint

    if annotations.attribution:
        result["attribution"] = list(annotations.attribution)

    if annotations.input_metadata:
        result["inputMetadata"] = _input_meta_to_wire(annotations.input_metadata)

    if annotations.return_metadata:
        result["returnMetadata"] = _return_meta_to_wire(annotations.return_metadata)

    return result


def from_wire(data: dict[str, Any]) -> TrustAnnotations:
    """Deserialize MCP wire format dict to TrustAnnotations.

    Parses the trust-related fields from a ToolAnnotations dict.
    Raises ``ValueError`` on malformed input.

        wire = {"maliciousActivityHint": True, "attribution": ["EHR"],
                "returnMetadata": {"source": "internal", "sensitivity": "pii"}}
        ann = from_wire(wire)
    """
    if not isinstance(data, dict):
        raise ValueError(f"from_wire() expects a dict, got {type(data).__name__}")

    # Validate maliciousActivityHint
    hint = data.get("maliciousActivityHint")
    if hint is not None and not isinstance(hint, bool):
        raise ValueError(
            f"maliciousActivityHint must be bool or null, got {type(hint).__name__}"
        )

    # Validate attribution
    raw_attr = data.get("attribution", ())
    if not isinstance(raw_attr, (list, tuple)):
        raise ValueError(
            f"attribution must be an array, got {type(raw_attr).__name__}"
        )
    for i, item in enumerate(raw_attr):
        if not isinstance(item, str):
            raise ValueError(
                f"attribution[{i}] must be a string, got {type(item).__name__}: {item!r}"
            )

    return TrustAnnotations(
        malicious_activity_hint=hint,
        attribution=tuple(raw_attr),
        input_metadata=_input_meta_from_wire(data["inputMetadata"])
        if "inputMetadata" in data
        else None,
        return_metadata=_return_meta_from_wire(data["returnMetadata"])
        if "returnMetadata" in data
        else None,
    )


# ---------------------------------------------------------------------------
# Internal: serialization helpers
# ---------------------------------------------------------------------------

def _sensitivity_to_wire(s: DataClass) -> str | dict[str, Any]:
    if isinstance(s, SimpleDataClass):
        return s.value
    elif isinstance(s, Regulated):
        return {"regulated": {"scopes": list(s.regulated.scopes)}}
    raise TypeError(f"Unknown DataClass type: {type(s)}")


def _sensitivity_from_wire(raw: str | dict[str, Any]) -> DataClass:
    if isinstance(raw, str):
        try:
            return SimpleDataClass(raw)
        except ValueError:
            valid = [e.value for e in SimpleDataClass]
            raise ValueError(
                f"Unknown sensitivity value {raw!r}; "
                f"expected one of {valid} or a regulated object"
            ) from None
    if isinstance(raw, dict) and "regulated" in raw:
        reg = raw["regulated"]
        if not isinstance(reg, dict) or "scopes" not in reg:
            raise ValueError(
                f"regulated must be an object with 'scopes', got: {reg!r}"
            )
        raw_scopes = reg["scopes"]
        if not isinstance(raw_scopes, (list, tuple)):
            raise ValueError(
                f"regulated.scopes must be an array, got {type(raw_scopes).__name__}"
            )
        for i, s in enumerate(raw_scopes):
            if not isinstance(s, str):
                raise ValueError(
                    f"regulated.scopes[{i}] must be a string, got {type(s).__name__}"
                )
        scopes = tuple(raw_scopes)
        from trust_types import RegulatoryScope
        return Regulated(RegulatoryScope(scopes))
    raise ValueError(f"Cannot parse DataClass from: {raw!r}")


def _enum_or_array_to_wire(val: Any) -> str | list[str]:
    """Convert a single enum or tuple of enums to wire format."""
    if isinstance(val, tuple):
        return [v.value for v in val]
    return val.value


def _sensitivity_or_array_to_wire(
    val: DataClass | tuple[DataClass, ...],
) -> str | dict | list:
    if isinstance(val, tuple):
        return [_sensitivity_to_wire(v) for v in val]
    return _sensitivity_to_wire(val)


def _input_meta_to_wire(m: InputMetadata) -> dict[str, Any]:
    return {
        "destination": _enum_or_array_to_wire(m.destination),
        "sensitivity": _sensitivity_or_array_to_wire(m.sensitivity),
        "outcomes": _enum_or_array_to_wire(m.outcomes),
    }


def _return_meta_to_wire(m: ReturnMetadata) -> dict[str, Any]:
    return {
        "source": _enum_or_array_to_wire(m.source),
        "sensitivity": _sensitivity_or_array_to_wire(m.sensitivity),
    }


def _enum_or_array_from_wire(raw: str | list[str], enum_cls: type) -> Any:
    if isinstance(raw, list):
        return tuple(enum_cls(v) for v in raw)
    return enum_cls(raw)


def _sensitivity_or_array_from_wire(
    raw: str | dict | list,
) -> DataClass | tuple[DataClass, ...]:
    if isinstance(raw, list):
        return tuple(_sensitivity_from_wire(v) for v in raw)
    return _sensitivity_from_wire(raw)


def _input_meta_from_wire(data: dict[str, Any]) -> InputMetadata:
    return InputMetadata(
        destination=_enum_or_array_from_wire(data.get("destination", "ephemeral"), Destination),
        sensitivity=_sensitivity_or_array_from_wire(data.get("sensitivity", "none")),
        outcomes=_enum_or_array_from_wire(data.get("outcomes", "benign"), Outcome),
    )


def _return_meta_from_wire(data: dict[str, Any]) -> ReturnMetadata:
    return ReturnMetadata(
        source=_enum_or_array_from_wire(data.get("source", "system"), Source),
        sensitivity=_sensitivity_or_array_from_wire(data.get("sensitivity", "none")),
    )
