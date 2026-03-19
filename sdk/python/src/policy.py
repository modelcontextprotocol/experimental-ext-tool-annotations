"""Policy engine — evaluate trust annotations against configurable rules.

Provides three enforcement modes:
  - audit:   log decisions, never block (default)
  - warn:    log decisions, surface warnings to the user
  - enforce: block tool calls that violate policy

The engine ships with sensible default rules but is fully extensible.

Usage:
    from policy import PolicyEngine
    from trust_types import TrustAnnotations

    engine = PolicyEngine(mode="enforce")

    # Register tools with their annotations
    engine.register_tool("patient_lookup", {"returnMetadata": {"sensitivity": "pii"}})

    # Evaluate before calling
    decision = engine.evaluate("patient_lookup", action="call")
    if not decision.allowed:
        print(f"Blocked: {decision.reason}")

    # Or use the convenience method
    engine.register_trust_annotations("send_email", trust_ann)
    decision = engine.evaluate(
        "send_email",
        action="call",
        target_destination="public",
        session=session_tracker.session,
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from emit import _emit_policy
from trust_types import (
    DataClass,
    Destination,
    Regulated,
    SessionAnnotations,
    SimpleDataClass,
    TrustAnnotations,
    sensitivity_level,
)


# ---------------------------------------------------------------------------
# Policy decision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDecision:
    """Result of evaluating a policy rule."""
    allowed: bool
    effect: str        # "allow" | "block" | "escalate" | "redact" | "warn"
    reason: str
    rule: str = ""     # which rule triggered
    regulations: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Rule interface
# ---------------------------------------------------------------------------

class PolicyRule(ABC):
    """Base class for policy rules.

    Implement evaluate() to return a PolicyDecision if the rule triggers,
    or None to pass through to the next rule.
    """
    name: str = "unnamed"

    @abstractmethod
    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        ...


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

class BlockCredentialsToPublic(PolicyRule):
    """Block sending credential-level data to public destinations."""
    name = "block-credentials-to-public"

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if target_destination != "public":
            return None
        sensitivity = _extract_sensitivity(annotations)
        if sensitivity and sensitivity_level(sensitivity) >= sensitivity_level(SimpleDataClass.CREDENTIALS):
            return PolicyDecision(
                allowed=False,
                effect="block",
                reason=f"Cannot send {sensitivity} data to public destination",
                rule=self.name,
            )
        return None


class BlockRegulatedToExternal(PolicyRule):
    """Block sending regulated data to public/external destinations."""
    name = "block-regulated-to-external"

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if target_destination not in ("public", "external"):
            return None
        sensitivity = _extract_sensitivity(annotations)
        if isinstance(sensitivity, Regulated):
            return PolicyDecision(
                allowed=False,
                effect="block",
                reason=f"Regulated data ({', '.join(sensitivity.regulated.scopes)}) cannot leave organization",
                rule=self.name,
                regulations=sensitivity.regulated.scopes,
            )
        return None


class WarnOnPIIForward(PolicyRule):
    """Warn when PII data is being forwarded to another tool."""
    name = "warn-pii-forward"

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if action != "forward":
            return None
        sensitivity = _extract_sensitivity(annotations)
        if sensitivity and sensitivity_level(sensitivity) >= sensitivity_level(SimpleDataClass.PII):
            return PolicyDecision(
                allowed=True,
                effect="warn",
                reason=f"Forwarding {sensitivity} data — ensure recipient has need-to-know",
                rule=self.name,
            )
        return None


class BlockMaliciousActivity(PolicyRule):
    """Block tool calls flagged as potentially malicious."""
    name = "block-malicious-activity"

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if annotations.get("maliciousActivityHint"):
            return PolicyDecision(
                allowed=False,
                effect="block",
                reason="Tool flagged for potential malicious activity",
                rule=self.name,
            )
        return None


class EscalateSessionSensitivity(PolicyRule):
    """Require escalation when session sensitivity exceeds threshold.

    When the session has accumulated sensitive data (e.g. PII) and
    the tool targets a less-restricted destination, escalate for
    human approval.
    """
    name = "escalate-session-sensitivity"

    def __init__(self, threshold: DataClass = SimpleDataClass.PII) -> None:
        self._threshold = threshold

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if session is None:
            return None
        if target_destination not in ("public", "external"):
            return None
        if sensitivity_level(session.max_sensitivity) >= sensitivity_level(self._threshold):
            return PolicyDecision(
                allowed=False,
                effect="escalate",
                reason=(
                    f"Session contains {session.max_sensitivity} "
                    f"data — outbound to '{target_destination}' requires approval"
                ),
                rule=self.name,
            )
        return None


class BlockOpenWorldToSensitiveWrite(PolicyRule):
    """Block writes to sensitive tools when session has seen untrusted content.

    Prevents prompt-injection-driven data corruption: if the session has
    consumed open-world (untrusted) content and the target tool is
    destructive with sensitive inputs, the call is blocked.

    This closes the gap where an attacker injects instructions into
    untrusted tool output (e.g. search results) that trick the LLM
    into calling a write tool with attacker-controlled arguments.
    """
    name = "block-openworld-to-sensitive-write"

    def __init__(self, threshold: DataClass = SimpleDataClass.PII) -> None:
        self._threshold = threshold

    def evaluate(
        self,
        annotations: dict[str, Any],
        action: str,
        target_destination: str | None,
        session: SessionAnnotations | None,
    ) -> PolicyDecision | None:
        if session is None or not session.open_world_hint:
            return None
        if not annotations.get("destructiveHint"):
            return None
        sensitivity = _extract_sensitivity(annotations)
        if sensitivity and sensitivity_level(sensitivity) >= sensitivity_level(self._threshold):
            return PolicyDecision(
                allowed=False,
                effect="block",
                reason=(
                    "Write to sensitive tool blocked: session contains "
                    "untrusted open-world content"
                ),
                rule=self.name,
            )
        return None


# Default rule set — ordered from most to least severe
DEFAULT_RULES: list[PolicyRule] = [
    BlockMaliciousActivity(),
    BlockCredentialsToPublic(),
    BlockRegulatedToExternal(),
    BlockOpenWorldToSensitiveWrite(),
    EscalateSessionSensitivity(),
    WarnOnPIIForward(),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Evaluates tool calls against a configurable set of policy rules.

    Modes:
      - audit:   decisions are logged but never enforced
      - warn:    "block" decisions become "warn" (logged, not enforced) — **default**
      - enforce: decisions are enforced as-is
    """

    def __init__(
        self,
        mode: str = "warn",
        rules: list[PolicyRule] | None = None,
        fail_closed: bool = False,
    ) -> None:
        if mode not in ("audit", "warn", "enforce"):
            raise ValueError(f"Invalid mode: {mode!r} — must be 'audit', 'warn', or 'enforce'")
        self.mode = mode
        self.fail_closed = fail_closed
        self._tools: dict[str, dict[str, Any]] = {}
        self._rules = rules if rules is not None else DEFAULT_RULES.copy()

    # -----------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------

    def register_tool(self, name: str, annotations: dict[str, Any]) -> None:
        """Register a tool's wire-format annotations dict."""
        self._tools[name] = annotations

    def register_trust_annotations(
        self, name: str, annotations: TrustAnnotations
    ) -> None:
        """Register a tool using typed TrustAnnotations."""
        from annotate import to_wire
        self._tools[name] = to_wire(annotations)

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a custom policy rule."""
        self._rules.append(rule)

    # -----------------------------------------------------------------
    # Evaluation
    # -----------------------------------------------------------------

    def evaluate(
        self,
        tool: str,
        action: str = "call",
        target_destination: str | None = None,
        session: SessionAnnotations | None = None,
    ) -> PolicyDecision:
        """Evaluate policy rules for a tool call.

        Args:
            tool: Tool name (must be registered).
            action: "call" | "forward" | "store" | etc.
            target_destination: Where the output will be sent.
            session: Current session annotations (for escalation rules).

        Returns:
            PolicyDecision with the first matching rule's verdict,
            adjusted for the engine's mode.
        """
        if tool not in self._tools:
            if self.fail_closed:
                decision = PolicyDecision(
                    allowed=False,
                    effect="block",
                    reason=f"Unregistered tool '{tool}' blocked by fail-closed policy",
                    rule="fail-closed",
                )
                _emit_policy(
                    tool=tool,
                    effect=decision.effect,
                    reason=decision.reason,
                    rule=decision.rule,
                    mode=self.mode,
                )
                return decision
            annotations: dict[str, Any] = {}
        else:
            annotations = self._tools[tool]

        for rule in self._rules:
            decision = rule.evaluate(annotations, action, target_destination, session)
            if decision is not None:
                final = self._apply_mode(decision)
                _emit_policy(
                    tool=tool,
                    effect=final.effect,
                    reason=final.reason,
                    rule=final.rule,
                    mode=self.mode,
                    original_effect=decision.effect,
                )
                return final

        return PolicyDecision(
            allowed=True,
            effect="allow",
            reason="No policy rule triggered",
        )

    # -----------------------------------------------------------------
    # Inspection
    # -----------------------------------------------------------------

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        """Copy of registered tool annotations."""
        return dict(self._tools)

    @property
    def rules(self) -> list[PolicyRule]:
        """Current rule list."""
        return list(self._rules)

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _apply_mode(self, decision: PolicyDecision) -> PolicyDecision:
        if self.mode == "enforce":
            return decision
        if self.mode == "warn":
            if decision.effect == "block" or decision.effect == "escalate":
                return PolicyDecision(
                    allowed=True,
                    effect="warn",
                    reason=f"[WARN] {decision.reason}",
                    rule=decision.rule,
                    regulations=decision.regulations,
                )
            return decision
        # audit mode — everything is allowed, just logged
        return PolicyDecision(
            allowed=True,
            effect="audit",
            reason=f"[AUDIT] {decision.reason}",
            rule=decision.rule,
            regulations=decision.regulations,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_sensitivity(annotations: dict[str, Any]) -> DataClass | None:
    """Extract the highest sensitivity from a wire-format annotations dict."""
    from annotate import _sensitivity_from_wire
    from trust_types import max_sensitivity as _max

    best: DataClass | None = None

    for key in ("inputMetadata", "returnMetadata"):
        meta = annotations.get(key, {})
        raw_sens = meta.get("sensitivity")
        if raw_sens is None:
            continue

        items = raw_sens if isinstance(raw_sens, list) else [raw_sens]
        for item in items:
            parsed = _sensitivity_from_wire(item)
            if best is None:
                best = parsed
            else:
                best = _max(best, parsed)

    return best
