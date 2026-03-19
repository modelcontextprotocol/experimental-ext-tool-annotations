"""Tests for mcp_trust.policy — policy engine and default rules."""

import pytest
from trust_types import (
    Regulated,
    SessionAnnotations,
    SimpleDataClass,
    TrustAnnotations,
    ReturnMetadata,
    InputMetadata,
    Source,
    Destination,
    Outcome,
)
from annotate import to_wire
from policy import (
    BlockCredentialsToPublic,
    BlockMaliciousActivity,
    BlockOpenWorldToSensitiveWrite,
    BlockRegulatedToExternal,
    EscalateSessionSensitivity,
    PolicyDecision,
    PolicyEngine,
    WarnOnPIIForward,
)


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

class TestBlockCredentialsToPublic:
    def test_blocks_credentials_to_public(self):
        rule = BlockCredentialsToPublic()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.SYSTEM,
                sensitivity=SimpleDataClass.CREDENTIALS,
            )
        ))
        decision = rule.evaluate(ann, "call", "public", None)
        assert decision is not None
        assert decision.allowed is False
        assert decision.effect == "block"

    def test_allows_credentials_to_internal(self):
        rule = BlockCredentialsToPublic()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.SYSTEM,
                sensitivity=SimpleDataClass.CREDENTIALS,
            )
        ))
        decision = rule.evaluate(ann, "call", "internal", None)
        assert decision is None  # no opinion


class TestBlockRegulatedToExternal:
    def test_blocks_regulated_to_public(self):
        rule = BlockRegulatedToExternal()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            )
        ))
        decision = rule.evaluate(ann, "call", "public", None)
        assert decision is not None
        assert decision.allowed is False
        assert "HIPAA" in decision.regulations

    def test_allows_regulated_to_internal(self):
        rule = BlockRegulatedToExternal()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            )
        ))
        decision = rule.evaluate(ann, "call", "internal", None)
        assert decision is None


class TestBlockMaliciousActivity:
    def test_blocks_malicious(self):
        rule = BlockMaliciousActivity()
        decision = rule.evaluate(
            {"maliciousActivityHint": True}, "call", None, None
        )
        assert decision is not None
        assert decision.allowed is False

    def test_allows_non_malicious(self):
        rule = BlockMaliciousActivity()
        decision = rule.evaluate({}, "call", None, None)
        assert decision is None


class TestWarnOnPIIForward:
    def test_warns_on_pii_forward(self):
        rule = WarnOnPIIForward()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.PII,
            )
        ))
        decision = rule.evaluate(ann, "forward", None, None)
        assert decision is not None
        assert decision.effect == "warn"
        assert decision.allowed is True

    def test_no_warn_on_call(self):
        rule = WarnOnPIIForward()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.PII,
            )
        ))
        decision = rule.evaluate(ann, "call", None, None)
        assert decision is None


class TestBlockOpenWorldToSensitiveWrite:
    def test_blocks_destructive_write_after_open_world(self):
        """Core scenario: untrusted content in session + destructive + sensitive input → BLOCK."""
        rule = BlockOpenWorldToSensitiveWrite()
        ann = to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ))
        ann["destructiveHint"] = True
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = rule.evaluate(ann, "call", "internal", session)
        assert decision is not None
        assert decision.allowed is False
        assert decision.effect == "block"
        assert "open-world" in decision.reason

    def test_allows_write_without_open_world(self):
        """No open-world content in session → no opinion."""
        rule = BlockOpenWorldToSensitiveWrite()
        ann = to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ))
        ann["destructiveHint"] = True
        session = SessionAnnotations()
        session.open_world_hint = False
        decision = rule.evaluate(ann, "call", "internal", session)
        assert decision is None

    def test_allows_read_only_tool_after_open_world(self):
        """Open-world session but tool is read-only (not destructive) → no opinion."""
        rule = BlockOpenWorldToSensitiveWrite()
        ann = to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
        ))
        # No destructiveHint
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = rule.evaluate(ann, "call", "internal", session)
        assert decision is None

    def test_allows_destructive_below_threshold(self):
        """Destructive + open-world but sensitivity below threshold → no opinion."""
        rule = BlockOpenWorldToSensitiveWrite()
        ann = to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.USER,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ))
        ann["destructiveHint"] = True
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = rule.evaluate(ann, "call", "internal", session)
        assert decision is None  # USER < PII threshold

    def test_custom_threshold(self):
        """Custom threshold still blocks at that level."""
        rule = BlockOpenWorldToSensitiveWrite(threshold=SimpleDataClass.FINANCIAL)
        ann = to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.PII,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ))
        ann["destructiveHint"] = True
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = rule.evaluate(ann, "call", "internal", session)
        assert decision is None  # PII < FINANCIAL threshold

    def test_no_session(self):
        """No session provided → no opinion."""
        rule = BlockOpenWorldToSensitiveWrite()
        ann = {"destructiveHint": True, "inputMetadata": {"sensitivity": "credentials"}}
        decision = rule.evaluate(ann, "call", "internal", None)
        assert decision is None


class TestEscalateSessionSensitivity:
    def test_escalates_when_session_has_pii_and_target_public(self):
        rule = EscalateSessionSensitivity()
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = rule.evaluate({}, "call", "public", session)
        assert decision is not None
        assert decision.effect == "escalate"
        assert decision.allowed is False

    def test_no_escalation_for_internal(self):
        rule = EscalateSessionSensitivity()
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = rule.evaluate({}, "call", "internal", session)
        assert decision is None

    def test_no_escalation_below_threshold(self):
        rule = EscalateSessionSensitivity()
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.USER
        decision = rule.evaluate({}, "call", "public", session)
        assert decision is None

    def test_custom_threshold(self):
        rule = EscalateSessionSensitivity(threshold=SimpleDataClass.FINANCIAL)
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = rule.evaluate({}, "call", "public", session)
        assert decision is None  # PII < FINANCIAL


# ---------------------------------------------------------------------------
# PolicyEngine modes
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def _make_engine(self, mode: str) -> PolicyEngine:
        engine = PolicyEngine(mode=mode)
        engine.register_tool("send_email", to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        )))
        engine.register_tool("patient_lookup", to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
        )))
        return engine

    def test_enforce_blocks(self):
        engine = self._make_engine("enforce")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public"
        )
        assert decision.allowed is False
        assert decision.effect == "block"

    def test_warn_converts_block_to_warn(self):
        engine = self._make_engine("warn")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public"
        )
        assert decision.allowed is True
        assert decision.effect == "warn"

    def test_audit_allows_everything(self):
        engine = self._make_engine("audit")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public"
        )
        assert decision.allowed is True
        assert decision.effect == "audit"

    def test_no_rule_triggered(self):
        engine = self._make_engine("enforce")
        decision = engine.evaluate("send_email", action="call", target_destination="internal")
        assert decision.allowed is True
        assert decision.effect == "allow"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            PolicyEngine(mode="invalid")

    def test_register_trust_annotations(self):
        engine = PolicyEngine(mode="enforce")
        ta = TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.SYSTEM,
                sensitivity=SimpleDataClass.CREDENTIALS,
            )
        )
        engine.register_trust_annotations("secret_tool", ta)
        decision = engine.evaluate("secret_tool", target_destination="public")
        assert decision.allowed is False

    def test_session_escalation(self):
        engine = self._make_engine("enforce")
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII

        # send_email to public with PII session → escalate
        decision = engine.evaluate(
            "send_email", action="call",
            target_destination="public",
            session=session,
        )
        assert decision.effect == "escalate"

    def test_default_mode_is_warn(self):
        engine = PolicyEngine()
        assert engine.mode == "warn"

    def test_fail_closed_blocks_unregistered_tool(self):
        engine = PolicyEngine(mode="enforce", fail_closed=True)
        engine.register_tool("known_tool", {})
        decision = engine.evaluate("unknown_tool", action="call")
        assert decision.allowed is False
        assert decision.effect == "block"
        assert "Unregistered tool" in decision.reason
        assert decision.rule == "fail-closed"

    def test_fail_open_allows_unregistered_tool(self):
        engine = PolicyEngine(mode="enforce", fail_closed=False)
        decision = engine.evaluate("unknown_tool", action="call")
        assert decision.allowed is True
        assert decision.effect == "allow"
