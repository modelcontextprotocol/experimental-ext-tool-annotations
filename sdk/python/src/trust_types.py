"""SEP-1913 Trust & Sensitivity Annotation types — 1:1 mapping to the spec.

All types are immutable (frozen dataclasses / enums).  This module is the
single source of truth for SEP-1913's schema in Python.  If the SEP changes,
update HERE first, then propagate to the rest of the SDK.

Wire format mapping (Python → JSON):
    Destination.EPHEMERAL   → "ephemeral"
    SimpleDataClass.PII     → "pii"
    Regulated(("HIPAA",))   → {"regulated": {"scopes": ["HIPAA"]}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Union


# ---------------------------------------------------------------------------
# Enums — map directly to SEP-1913 string unions
# ---------------------------------------------------------------------------

class Destination(str, Enum):
    """Where tool inputs are sent / stored (InputMetadata.destination)."""
    EPHEMERAL = "ephemeral"
    SYSTEM = "system"
    USER = "user"
    INTERNAL = "internal"
    PUBLIC = "public"


class Source(str, Enum):
    """Where tool outputs originate from (ReturnMetadata.source)."""
    UNTRUSTED_PUBLIC = "untrustedPublic"
    TRUSTED_PUBLIC = "trustedPublic"
    INTERNAL = "internal"
    USER = "user"
    SYSTEM = "system"


class Outcome(str, Enum):
    """Consequence severity of a tool invocation (InputMetadata.outcomes)."""
    BENIGN = "benign"
    CONSEQUENTIAL = "consequential"
    IRREVERSIBLE = "irreversible"


class SimpleDataClass(str, Enum):
    """Built-in data classification categories."""
    NONE = "none"
    USER = "user"
    PII = "pii"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"


# ---------------------------------------------------------------------------
# Composite types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatoryScope:
    """A set of regulatory compliance scopes (e.g. HIPAA, GDPR, PCI-DSS).

    Stored as a tuple for immutability and hashability.
    """
    scopes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scopes:
            raise ValueError("RegulatoryScope must have at least one scope")


@dataclass(frozen=True)
class Regulated:
    """DataClass variant for regulated data — wraps RegulatoryScope.

    Wire format: {"regulated": {"scopes": ["HIPAA", "SOX"]}}
    """
    regulated: RegulatoryScope

    @classmethod
    def of(cls, *scopes: str) -> Regulated:
        """Convenience constructor: Regulated.of("HIPAA", "SOX")."""
        return cls(RegulatoryScope(scopes))


# The union type matching SEP-1913's DataClass
DataClass = Union[SimpleDataClass, Regulated]


# ---------------------------------------------------------------------------
# Sensitivity ordering (for propagation escalation)
# ---------------------------------------------------------------------------

_SIMPLE_ORDER: dict[SimpleDataClass, int] = {
    SimpleDataClass.NONE: 0,
    SimpleDataClass.USER: 1,
    SimpleDataClass.PII: 2,
    SimpleDataClass.FINANCIAL: 3,
    SimpleDataClass.CREDENTIALS: 4,
}

_REGULATED_ORDER = 5  # regulated(*) is always highest


def sensitivity_level(dc: DataClass) -> int:
    """Return a numeric ordering for DataClass values.

    Used by the session propagation tracker to compute
    session-max sensitivity.

    Ordering: none(0) < user(1) < pii(2) < financial(3)
              < credentials(4) < regulated(*)(5)
    """
    if isinstance(dc, SimpleDataClass):
        return _SIMPLE_ORDER[dc]
    return _REGULATED_ORDER


def max_sensitivity(a: DataClass, b: DataClass) -> DataClass:
    """Return the higher-sensitivity DataClass value.

    For two Regulated values, merges their scopes.
    """
    la, lb = sensitivity_level(a), sensitivity_level(b)
    if la > lb:
        return a
    if lb > la:
        return b
    # Equal level — if both regulated, merge scopes
    if isinstance(a, Regulated) and isinstance(b, Regulated):
        merged = set(a.regulated.scopes) | set(b.regulated.scopes)
        return Regulated(RegulatoryScope(tuple(sorted(merged))))
    return a  # same simple level, same value


# ---------------------------------------------------------------------------
# Action Security Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InputMetadata:
    """Describes where tool inputs go and their security implications.

    Corresponds to SEP-1913's InputMetadata interface.
    Fields accept either a single value or a tuple of values
    (representing a possible set for tools/list declarations).
    """
    destination: Destination | tuple[Destination, ...] = Destination.EPHEMERAL
    sensitivity: DataClass | tuple[DataClass, ...] = SimpleDataClass.NONE
    outcomes: Outcome | tuple[Outcome, ...] = Outcome.BENIGN


@dataclass(frozen=True)
class ReturnMetadata:
    """Describes where tool outputs come from and their sensitivity.

    Corresponds to SEP-1913's ReturnMetadata interface.
    """
    source: Source | tuple[Source, ...] = Source.SYSTEM
    sensitivity: DataClass | tuple[DataClass, ...] = SimpleDataClass.NONE


# ---------------------------------------------------------------------------
# Trust Annotations (extends ToolAnnotations)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustAnnotations:
    """SEP-1913 trust extension fields for ToolAnnotations.

    These are declared on tools/list and narrowed on tools/resolve.
    """
    malicious_activity_hint: bool | None = None
    attribution: tuple[str, ...] = ()
    input_metadata: InputMetadata | None = None
    return_metadata: ReturnMetadata | None = None


# ---------------------------------------------------------------------------
# Result & Session Annotations (propagation layer)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultAnnotations:
    """Annotations returned in CallToolResult._meta.annotations.

    Immutable — produced per tool call, then merged into
    SessionAnnotations via propagation rules.
    """
    open_world_hint: bool = False
    malicious_activity_hint: bool = False
    attribution: tuple[str, ...] = ()
    sensitivity: DataClass = SimpleDataClass.NONE


@dataclass
class SessionAnnotations:
    """Accumulated annotations across an agent session.

    Mutable — grows monotonically as the session progresses.
    Implements SEP-1913 propagation rules:
      - Boolean union for openWorldHint
      - Boolean union for maliciousActivityHint
      - Attribution accumulation (set union)
      - Sensitivity escalation (session max)
    """
    open_world_hint: bool = False
    malicious_activity_hint: bool = False
    attribution: set[str] = field(default_factory=set)
    max_sensitivity: DataClass = SimpleDataClass.NONE

    def merge(self, result: ResultAnnotations) -> None:
        """Apply propagation rules from a tool call result."""
        if result.open_world_hint:
            self.open_world_hint = True
        if result.malicious_activity_hint:
            self.malicious_activity_hint = True
        self.attribution.update(result.attribution)
        self.max_sensitivity = max_sensitivity(
            self.max_sensitivity, result.sensitivity
        )
