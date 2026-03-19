"""SEP-1913 Usability Scenario Test Suite.

Each scenario class combines a *participant worksheet* (the class docstring)
with *SDK oracle tests* (the test methods).  To run a spec-clarity study:

1. Hand participants USABILITY_SCENARIOS.md + the SEP-1913 spec.
2. Collect their answers.
3. Run this file to produce the correct answers.
4. Compute the delta — low agreement highlights spec ambiguities.

Run:
    cd packages/python
    PYTHONPATH=src pytest tests/test_usability_scenarios.py -v
"""

from trust_types import (
    Destination,
    InputMetadata,
    Outcome,
    Regulated,
    ResultAnnotations,
    ReturnMetadata,
    SessionAnnotations,
    SimpleDataClass,
    Source,
    TrustAnnotations,
    sensitivity_level,
)
from propagate import SessionTracker
from policy import PolicyEngine, PolicyDecision
from annotate import to_wire, from_wire


# ===================================================================
# Scenario 1 — Classification: Simple Email Send Tool
# Spec section: InputMetadata, ReturnMetadata, Destination, Outcome, Source
# Expected agreement: HIGH
# ===================================================================

class TestScenario01_SimpleToolClassification:
    """SCENARIO 1 — Simple: Email Send Tool

    Context:
        You are implementing an MCP server that exposes a `send_email` tool.
        This tool accepts a recipient address and message body, sends the
        email via SMTP, and returns a delivery receipt from the mail server.

    Questions:
        Q1. What Destination should `send_email` use?
            a) ephemeral  b) system  c) user  d) internal  e) public

        Q2. What Outcome should `send_email` use?
            a) benign  b) consequential  c) irreversible

        Q3. What Source should the return metadata use?
            a) untrustedPublic  b) trustedPublic  c) internal  d) user  e) system

    Your answers:
        Q1: ___   Q2: ___   Q3: ___
    """

    def test_destination_is_public(self):
        """Email leaves the organization boundary → public."""
        meta = InputMetadata(
            destination=Destination.PUBLIC,
            sensitivity=SimpleDataClass.NONE,
            outcomes=Outcome.IRREVERSIBLE,
        )
        assert meta.destination == Destination.PUBLIC

    def test_outcome_is_irreversible(self):
        """Once sent, an email cannot be recalled → irreversible."""
        meta = InputMetadata(
            destination=Destination.PUBLIC,
            outcomes=Outcome.IRREVERSIBLE,
        )
        assert meta.outcomes == Outcome.IRREVERSIBLE

    def test_source_is_system(self):
        """Delivery receipt comes from the mail server (trusted infra) → system."""
        meta = ReturnMetadata(
            source=Source.SYSTEM,
            sensitivity=SimpleDataClass.NONE,
        )
        assert meta.source == Source.SYSTEM

    def test_full_annotation_roundtrip(self):
        """Verify the complete annotation serializes correctly."""
        ann = TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.IRREVERSIBLE,
            ),
            return_metadata=ReturnMetadata(
                source=Source.SYSTEM,
                sensitivity=SimpleDataClass.NONE,
            ),
        )
        wire = to_wire(ann)
        restored = from_wire(wire)
        assert restored.input_metadata.destination == Destination.PUBLIC
        assert restored.input_metadata.outcomes == Outcome.IRREVERSIBLE
        assert restored.return_metadata.source == Source.SYSTEM


# ===================================================================
# Scenario 2 — Classification: Ambiguous Save to Workspace
# Spec section: Destination enum boundary
# Expected agreement: LOW (deliberate ambiguity)
# ===================================================================

class TestScenario02_AmbiguousSaveToWorkspace:
    """SCENARIO 2 — Ambiguous: Save to Workspace

    Context:
        Your tool `save_to_workspace` writes a document to a shared
        team workspace.  The workspace is accessible to all team
        members (not just the invoking user) but is NOT accessible
        outside the organization.

    Questions:
        Q1. What Destination should this tool use?
            a) ephemeral  b) system  c) user  d) internal  e) public

        Q2. Justify your choice — what distinguishes `user` from `internal`
            in this scenario?

    Your answers:
        Q1: ___
        Q2: _______________________________________________
    """

    def test_destination_is_internal(self):
        """Team-visible but org-internal → internal (not user, not public)."""
        meta = InputMetadata(
            destination=Destination.INTERNAL,
            sensitivity=SimpleDataClass.NONE,
            outcomes=Outcome.CONSEQUENTIAL,
        )
        assert meta.destination == Destination.INTERNAL

    def test_not_user_destination(self):
        """'user' implies single-user visibility; team workspace is broader."""
        assert Destination.INTERNAL != Destination.USER

    def test_not_public_destination(self):
        """Team workspace is inside the org boundary → not public."""
        assert Destination.INTERNAL != Destination.PUBLIC


# ===================================================================
# Scenario 3 — Propagation: Sensitivity Monotonic Escalation
# Spec section: Propagation Rules (sensitivity — GAP: not explicitly listed)
# Expected agreement: HIGH (intuitive, but spec may not state it)
# ===================================================================

class TestScenario03_SensitivityMonotonicEscalation:
    """SCENARIO 3 — Sensitivity Monotonic Escalation

    Context:
        In an agent session, Tool A returns sensitivity="pii".
        Then Tool B returns sensitivity="none".

    Questions:
        Q1. After both calls, what is the session's max_sensitivity?
            a) none  b) pii

        Q2. Can a later tool call ever DECREASE the session sensitivity?
            a) yes  b) no

        Q3. Does the spec's Propagation Rules section explicitly define
            sensitivity tracking?
            a) yes  b) no

    Your answers:
        Q1: ___   Q2: ___   Q3: ___
    """

    def test_session_retains_highest_sensitivity(self):
        """PII followed by NONE → session max stays PII."""
        tracker = SessionTracker(session_id="test-s03")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII), "tool_a")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE), "tool_b")
        assert tracker.session.max_sensitivity == SimpleDataClass.PII

    def test_sensitivity_never_decreases(self):
        """Monotonic escalation: sensitivity level can only go up."""
        tracker = SessionTracker(session_id="test-s03-mono")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.CREDENTIALS), "tool_x")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.USER), "tool_y")
        # CREDENTIALS (level 4) > USER (level 1) → stays CREDENTIALS
        assert tracker.session.max_sensitivity == SimpleDataClass.CREDENTIALS
        assert sensitivity_level(tracker.session.max_sensitivity) == 4

    def test_escalation_across_multiple_levels(self):
        """NONE → USER → PII → FINANCIAL → session tracks the max at each step."""
        tracker = SessionTracker(session_id="test-s03-multi")
        for sdc in [SimpleDataClass.NONE, SimpleDataClass.USER,
                     SimpleDataClass.PII, SimpleDataClass.FINANCIAL]:
            tracker.merge(ResultAnnotations(sensitivity=sdc), "tool")
        assert tracker.session.max_sensitivity == SimpleDataClass.FINANCIAL


# ===================================================================
# Scenario 4 — Propagation: openWorldHint Persistence
# Spec section: Propagation Rules §1 — boolean union
# Expected agreement: HIGH
# ===================================================================

class TestScenario04_OpenWorldHintPersistence:
    """SCENARIO 4 — openWorldHint Persistence

    Context:
        Tool A returns openWorldHint=true.
        Tool B returns openWorldHint=false.

    Questions:
        Q1. After both calls, what is the session's openWorldHint?
            a) true  b) false

        Q2. Which propagation rule governs this?
            a) boolean union  b) set union  c) max-sensitivity  d) not defined

    Your answers:
        Q1: ___   Q2: ___
    """

    def test_open_world_hint_sticky_true(self):
        """Boolean union: once true, stays true regardless of later false."""
        tracker = SessionTracker(session_id="test-s04")
        tracker.merge(ResultAnnotations(open_world_hint=True), "tool_a")
        tracker.merge(ResultAnnotations(open_world_hint=False), "tool_b")
        assert tracker.session.open_world_hint is True

    def test_false_then_true_also_sticky(self):
        """Order doesn't matter — boolean union is commutative."""
        tracker = SessionTracker(session_id="test-s04-reverse")
        tracker.merge(ResultAnnotations(open_world_hint=False), "tool_b")
        tracker.merge(ResultAnnotations(open_world_hint=True), "tool_a")
        assert tracker.session.open_world_hint is True

    def test_all_false_stays_false(self):
        """If no tool ever sets openWorldHint=true, session stays false."""
        tracker = SessionTracker(session_id="test-s04-allfalse")
        tracker.merge(ResultAnnotations(open_world_hint=False), "tool_1")
        tracker.merge(ResultAnnotations(open_world_hint=False), "tool_2")
        assert tracker.session.open_world_hint is False


# ===================================================================
# Scenario 5 — Policy: Data Exfiltration (PII Session + Public Dest)
# Spec section: EscalateSessionSensitivity rule with session context
# Expected agreement: MEDIUM
# ===================================================================

class TestScenario05_DataExfiltrationPIIToPublic:
    """SCENARIO 5 — Data Exfiltration: PII Session → Public Destination

    Context:
        An agent session has accumulated max_sensitivity="pii" from
        earlier tool calls.  The agent now wants to call `send_email`,
        which is annotated with:
          - inputMetadata.destination = "public"
          - inputMetadata.sensitivity = "none"
          - inputMetadata.outcomes = "consequential"

        The PolicyEngine is in "enforce" mode with default rules.

    Questions:
        Q1. Does BlockCredentialsToPublic fire?
            a) yes  b) no — why?

        Q2. Does EscalateSessionSensitivity fire?
            a) yes  b) no — why?

        Q3. What is the expected PolicyDecision?
            allowed: ___   effect: ___   rule: ___

    Your answers:
        Q1: ___   reason: _______________________________
        Q2: ___   reason: _______________________________
        Q3: allowed=___  effect="___"  rule="___"
    """

    def _make_engine(self):
        engine = PolicyEngine(mode="enforce")
        engine.register_tool("send_email", to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        )))
        return engine

    def test_block_credentials_does_not_fire(self):
        """send_email tool sensitivity is NONE (level 0) < CREDENTIALS (level 4)."""
        engine = self._make_engine()
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = engine.evaluate(
            "send_email", action="call",
            target_destination="public", session=session,
        )
        # If BlockCredentialsToPublic had fired, effect would be "block"
        assert decision.rule != "block-credentials-to-public"

    def test_escalate_session_sensitivity_fires(self):
        """Session PII (level 2) >= threshold PII (level 2), dest=public → escalate."""
        engine = self._make_engine()
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = engine.evaluate(
            "send_email", action="call",
            target_destination="public", session=session,
        )
        assert decision.allowed is False
        assert decision.effect == "escalate"
        assert decision.rule == "escalate-session-sensitivity"

    def test_key_insight_tool_vs_session_sensitivity(self):
        """The critical distinction: tool sensitivity (NONE) vs session
        sensitivity (PII).

        BlockCredentialsToPublic checks _extract_sensitivity (tool-level).
        EscalateSessionSensitivity checks session.max_sensitivity.
        """
        engine = self._make_engine()
        # With no session, no escalation rule fires either
        decision_no_session = engine.evaluate(
            "send_email", action="call", target_destination="public",
        )
        assert decision_no_session.allowed is True
        assert decision_no_session.effect == "allow"


# ===================================================================
# Scenario 6 — Policy: Prompt Injection (Open World + Destructive)
# Spec section: BlockOpenWorldToSensitiveWrite rule
# Expected agreement: MEDIUM
# ===================================================================

class TestScenario06_PromptInjectionOpenWorldDestructive:
    """SCENARIO 6 — Prompt Injection: Open World + Destructive Write

    Context:
        An agent session has openWorldHint=true (it read untrusted web
        content earlier).  The agent now wants to call
        `update_patient_record`, annotated with:
          - destructiveHint = true
          - inputMetadata.sensitivity = regulated(["HIPAA"])
          - inputMetadata.destination = "internal"

        The PolicyEngine is in "enforce" mode with default rules.

    Questions:
        Q1. Which rule fires first?
            a) block-credentials-to-public
            b) block-regulated-to-external
            c) block-openworld-to-sensitive-write
            d) escalate-session-sensitivity

        Q2. What is the expected PolicyDecision?
            allowed: ___   effect: ___   rule: ___

        Q3. Why don't the "to-public" rules fire?

    Your answers:
        Q1: ___
        Q2: allowed=___  effect="___"  rule="___"
        Q3: _______________________________________________
    """

    def _make_engine(self):
        engine = PolicyEngine(mode="enforce")
        ann = to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ))
        ann["destructiveHint"] = True
        engine.register_tool("update_patient_record", ann)
        return engine

    def test_block_openworld_fires(self):
        """Open-world session + destructive + HIPAA input → blocked."""
        engine = self._make_engine()
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = engine.evaluate(
            "update_patient_record", action="call",
            target_destination="internal", session=session,
        )
        assert decision.allowed is False
        assert decision.effect == "block"
        assert decision.rule == "block-openworld-to-sensitive-write"

    def test_no_block_without_open_world(self):
        """Same tool but session has no open-world content → allowed."""
        engine = self._make_engine()
        session = SessionAnnotations()
        session.open_world_hint = False
        decision = engine.evaluate(
            "update_patient_record", action="call",
            target_destination="internal", session=session,
        )
        assert decision.allowed is True
        assert decision.effect == "allow"

    def test_credentials_rule_skipped_for_internal_dest(self):
        """BlockCredentialsToPublic only checks target_destination='public'."""
        engine = self._make_engine()
        session = SessionAnnotations()
        session.open_world_hint = True
        decision = engine.evaluate(
            "update_patient_record", action="call",
            target_destination="internal", session=session,
        )
        assert decision.rule != "block-credentials-to-public"
        assert decision.rule != "block-regulated-to-external"


# ===================================================================
# Scenario 7 — Policy: Mode Behavior (enforce vs warn vs audit)
# Spec section: PolicyEngine mode transformation (_apply_mode)
# Expected agreement: MEDIUM
# ===================================================================

class TestScenario07_ModeBehavior:
    """SCENARIO 7 — Mode Behavior: enforce vs warn vs audit

    Context:
        A `patient_lookup` tool is annotated with:
          - returnMetadata.source = "internal"
          - returnMetadata.sensitivity = regulated(["HIPAA"])

        An agent calls it with target_destination="public".
        The default rules are loaded.

    Questions:
        Q1. Which default rule fires first?
            a) block-credentials-to-public
            b) block-regulated-to-external
            (Hint: consider the sensitivity ordering and rule eval order)

        Q2. In enforce mode: allowed=___  effect="___"
        Q3. In warn mode:    allowed=___  effect="___"
        Q4. In audit mode:   allowed=___  effect="___"

    Your answers:
        Q1: ___
        Q2: allowed=___  effect="___"
        Q3: allowed=___  effect="___"
        Q4: allowed=___  effect="___"
    """

    def _make_engine(self, mode):
        engine = PolicyEngine(mode=mode)
        engine.register_tool("patient_lookup", to_wire(TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
        )))
        return engine

    def test_credentials_rule_fires_first(self):
        """Regulated (level 5) >= CREDENTIALS (level 4) → BlockCredentialsToPublic fires.

        BlockCredentialsToPublic is evaluated BEFORE BlockRegulatedToExternal
        in DEFAULT_RULES order, and Regulated.of("HIPAA") has level 5 which
        is >= level 4 (CREDENTIALS threshold).
        """
        engine = self._make_engine("enforce")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public",
        )
        assert decision.rule == "block-credentials-to-public"

    def test_enforce_blocks(self):
        """Enforce mode: decision enforced as-is → blocked."""
        engine = self._make_engine("enforce")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public",
        )
        assert decision.allowed is False
        assert decision.effect == "block"

    def test_warn_converts_to_warn(self):
        """Warn mode: 'block' becomes 'warn', allowed=True."""
        engine = self._make_engine("warn")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public",
        )
        assert decision.allowed is True
        assert decision.effect == "warn"
        assert decision.rule == "block-credentials-to-public"

    def test_audit_converts_to_audit(self):
        """Audit mode: everything becomes 'audit', allowed=True."""
        engine = self._make_engine("audit")
        decision = engine.evaluate(
            "patient_lookup", action="call", target_destination="public",
        )
        assert decision.allowed is True
        assert decision.effect == "audit"
        assert decision.rule == "block-credentials-to-public"

    def test_warn_also_converts_escalate(self):
        """Warn mode converts BOTH 'block' AND 'escalate' to 'warn'."""
        engine = PolicyEngine(mode="warn")
        engine.register_tool("send_email", to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        )))
        session = SessionAnnotations()
        session.max_sensitivity = SimpleDataClass.PII
        decision = engine.evaluate(
            "send_email", action="call",
            target_destination="public", session=session,
        )
        assert decision.allowed is True
        assert decision.effect == "warn"
        assert decision.rule == "escalate-session-sensitivity"


# ===================================================================
# Scenario 8 — Gap: Sensitivity Propagation Missing from Spec
# Spec section: Propagation Rules completeness
# Expected agreement: LOW (tests a spec gap)
# ===================================================================

class TestScenario08_SensitivityPropagationGap:
    """SCENARIO 8 — Sensitivity Propagation Gap

    Context:
        Read the Propagation Rules section of SEP-1913 carefully.
        It defines propagation for:
          - openWorldHint (boolean union)
          - attribution (set union)

    Questions:
        Q1. Does the Propagation Rules section explicitly define how
            sensitivity propagates across tool calls?
            a) yes  b) no

        Q2. Despite Q1, does the SDK implement sensitivity propagation?
            a) yes  b) no

        Q3. If there is a gap, what propagation rule SHOULD apply
            to sensitivity?
            a) boolean union  b) set union  c) max ordering  d) not applicable

    Your answers:
        Q1: ___   Q2: ___   Q3: ___
    """

    def test_sdk_implements_sensitivity_propagation(self):
        """The SDK tracks max_sensitivity even though the spec's
        Propagation Rules section does not explicitly list it."""
        tracker = SessionTracker(session_id="test-s08")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII), "tool_a")
        assert tracker.session.max_sensitivity == SimpleDataClass.PII

    def test_sensitivity_uses_max_ordering(self):
        """SDK uses max-ordering (not boolean union or set union)."""
        tracker = SessionTracker(session_id="test-s08-max")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.USER), "t1")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.FINANCIAL), "t2")
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII), "t3")
        # FINANCIAL (level 3) > PII (level 2) > USER (level 1)
        assert tracker.session.max_sensitivity == SimpleDataClass.FINANCIAL

    def test_propagation_rules_do_define_boolean_union(self):
        """Confirm that boolean union IS defined for openWorldHint
        (to contrast with sensitivity which is NOT defined)."""
        tracker = SessionTracker(session_id="test-s08-owh")
        tracker.merge(ResultAnnotations(open_world_hint=True), "t1")
        tracker.merge(ResultAnnotations(open_world_hint=False), "t2")
        assert tracker.session.open_world_hint is True

    def test_propagation_rules_do_define_attribution_union(self):
        """Confirm that attribution set union IS defined."""
        tracker = SessionTracker(session_id="test-s08-attr")
        tracker.merge(ResultAnnotations(attribution=("A",)), "t1")
        tracker.merge(ResultAnnotations(attribution=("B",)), "t2")
        assert tracker.session.attribution == {"A", "B"}


# ===================================================================
# Scenario 9 — Gap: Host-Detected PII (Server Says "none")
# Spec section: Client Responsibilities #5, Security Implications
# Expected agreement: LOW (tests a spec gap)
# ===================================================================

class TestScenario09_HostDetectedPII:
    """SCENARIO 9 — Host-Detected PII (Server says "none")

    Context:
        A tool server returns sensitivity="none" in its result annotations.
        However, the host application's own PII scanner detects Social
        Security Numbers in the tool's output.

    Questions:
        Q1. Should the client trust the server's sensitivity="none"?
            a) yes (server is authoritative)
            b) no (defense-in-depth)

        Q2. Does the spec define a mechanism for the host to override
            or augment the server's sensitivity annotation?
            a) yes  b) no

        Q3. If the host rewrites sensitivity from "none" to "pii",
            what is lost?
            a) nothing  b) provenance (who classified it)
            c) attribution  d) all of the above

        Q4. What would a clean mechanism look like?
            _______________________________________________

    Your answers:
        Q1: ___   Q2: ___   Q3: ___
        Q4: _______________________________________________
    """

    def test_result_annotations_have_no_host_override_field(self):
        """ResultAnnotations has no field for host-detected sensitivity.
        The only sensitivity field is the server-provided one."""
        result = ResultAnnotations(sensitivity=SimpleDataClass.NONE)
        assert result.sensitivity == SimpleDataClass.NONE
        assert not hasattr(result, "host_sensitivity")
        assert not hasattr(result, "override_sensitivity")

    def test_host_can_construct_higher_sensitivity_result(self):
        """A host CAN create a new ResultAnnotations with higher sensitivity,
        but this loses provenance (no way to indicate 'host-detected')."""
        server_result = ResultAnnotations(sensitivity=SimpleDataClass.NONE)
        # Host scanner finds PII — constructs override
        host_override = ResultAnnotations(sensitivity=SimpleDataClass.PII)
        assert sensitivity_level(host_override.sensitivity) > sensitivity_level(
            server_result.sensitivity
        )

    def test_session_tracker_accepts_host_override(self):
        """SessionTracker merges whatever ResultAnnotations it receives,
        regardless of who constructed them."""
        tracker = SessionTracker(session_id="test-s09")
        # Merge the host-overridden result instead of the server result
        tracker.merge(
            ResultAnnotations(sensitivity=SimpleDataClass.PII),
            "tool_with_ssns",
        )
        assert tracker.session.max_sensitivity == SimpleDataClass.PII


# ===================================================================
# Scenario 10 — Gap: maliciousActivityHint — HITL vs Propagation
# Spec section: maliciousActivityHint semantics, boolean union
# Expected agreement: LOW (tests debatable design choice)
# ===================================================================

class TestScenario10_MaliciousActivityHintSemantics:
    """SCENARIO 10 — maliciousActivityHint: HITL vs Propagation

    Context:
        A tool server returns maliciousActivityHint=true in a
        CallToolResult's annotations.

    Questions:
        Q1. What should the client do with this hint?
            a) Surface it to the human user (HITL)
            b) Propagate it into session state via boolean union
            c) Both a and b
            d) Ignore it

        Q2. Should maliciousActivityHint propagate into session state
            the same way openWorldHint does (boolean union)?
            a) yes  b) no — why not?

        Q3. If it propagates, what happens when a LATER tool call
            in the same session is evaluated by the policy engine?
            _______________________________________________

        Q4. Does the spec explicitly define propagation behavior
            for maliciousActivityHint?
            a) yes  b) no

    Your answers:
        Q1: ___   Q2: ___   Q4: ___
        Q3: _______________________________________________
    """

    def test_sdk_propagates_malicious_hint(self):
        """The SDK DOES propagate maliciousActivityHint via boolean union.
        This is the current behavior, even though one can argue it
        should only trigger HITL and not persist in session state."""
        tracker = SessionTracker(session_id="test-s10")
        tracker.merge(
            ResultAnnotations(malicious_activity_hint=True), "suspicious_tool"
        )
        assert tracker.session.malicious_activity_hint is True

    def test_malicious_hint_is_sticky(self):
        """Once true, maliciousActivityHint stays true (boolean union)."""
        tracker = SessionTracker(session_id="test-s10-sticky")
        tracker.merge(
            ResultAnnotations(malicious_activity_hint=True), "bad_tool"
        )
        tracker.merge(
            ResultAnnotations(malicious_activity_hint=False), "good_tool"
        )
        assert tracker.session.malicious_activity_hint is True

    def test_malicious_session_does_not_block_clean_tools(self):
        """BlockMaliciousActivity checks the TOOL annotation, not session.
        A clean tool in a 'malicious' session is NOT blocked by this rule."""
        engine = PolicyEngine(mode="enforce")
        engine.register_tool("clean_tool", to_wire(TrustAnnotations()))
        engine.register_tool("suspect_tool", {"maliciousActivityHint": True})

        session = SessionAnnotations()
        session.malicious_activity_hint = True

        # Clean tool is NOT blocked (rule checks tool annotation, not session)
        d1 = engine.evaluate("clean_tool", session=session)
        assert d1.allowed is True

        # Suspect tool IS blocked (tool annotation has maliciousActivityHint)
        d2 = engine.evaluate("suspect_tool", session=session)
        assert d2.allowed is False
        assert d2.rule == "block-malicious-activity"

    def test_no_session_policy_for_malicious_session(self):
        """There is no default rule that checks session.malicious_activity_hint.

        BlockMaliciousActivity only checks the tool's annotations dict,
        not the session.  This is a potential gap — should there be a
        session-level malicious activity rule?"""
        engine = PolicyEngine(mode="enforce")
        engine.register_tool("innocent_tool", to_wire(TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.NONE,
            ),
        )))

        session = SessionAnnotations()
        session.malicious_activity_hint = True

        decision = engine.evaluate(
            "innocent_tool", action="call",
            target_destination="internal", session=session,
        )
        # Session is "malicious" but no rule checks session for this
        assert decision.allowed is True
        assert decision.effect == "allow"
