"""Tests for mcp_trust.propagate — session propagation tracker."""

import pytest
from trust_types import (
    Regulated,
    ResultAnnotations,
    SimpleDataClass,
)
from propagate import SessionTracker


class TestSessionTracker:
    def test_initial_state(self):
        tracker = SessionTracker(session_id="test-session")
        assert tracker.session_id == "test-session"
        assert tracker.call_count == 0
        assert tracker.has_seen_sensitive_data() is False

    def test_merge_escalates_sensitivity(self):
        tracker = SessionTracker()
        tracker.merge(
            ResultAnnotations(sensitivity=SimpleDataClass.PII),
            tool_name="patient_lookup",
        )
        assert tracker.session.max_sensitivity == SimpleDataClass.PII
        assert tracker.call_count == 1
        assert tracker.has_seen_sensitive_data() is True

    def test_cannot_deescalate(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.CREDENTIALS))
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE))
        assert tracker.session.max_sensitivity == SimpleDataClass.CREDENTIALS

    def test_escalation_to_regulated(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        tracker.merge(ResultAnnotations(sensitivity=Regulated.of("HIPAA")))
        assert isinstance(tracker.session.max_sensitivity, Regulated)

    def test_attribution_accumulates(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(attribution=("EHR",)))
        tracker.merge(ResultAnnotations(attribution=("Billing", "EHR")))
        assert tracker.session.attribution == {"EHR", "Billing"}

    def test_open_world_hint_sticky(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(open_world_hint=True))
        tracker.merge(ResultAnnotations(open_world_hint=False))
        assert tracker.session.open_world_hint is True

    def test_sensitivity_at_least(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        assert tracker.sensitivity_at_least(SimpleDataClass.USER) is True
        assert tracker.sensitivity_at_least(SimpleDataClass.PII) is True
        assert tracker.sensitivity_at_least(SimpleDataClass.CREDENTIALS) is False

    def test_get_regulatory_scopes_empty(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        assert tracker.get_regulatory_scopes() == ()

    def test_get_regulatory_scopes(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=Regulated.of("HIPAA", "SOX")))
        assert set(tracker.get_regulatory_scopes()) == {"HIPAA", "SOX"}

    def test_to_wire(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(
            open_world_hint=True,
            attribution=("EHR",),
            sensitivity=SimpleDataClass.PII,
        ))
        wire = tracker.to_wire()
        assert wire["openWorldHint"] is True
        assert wire["attribution"] == ["EHR"]
        assert wire["maxSensitivity"] == "pii"

    def test_to_wire_empty(self):
        tracker = SessionTracker()
        assert tracker.to_wire() == {}

    def test_summary(self):
        tracker = SessionTracker(session_id="s1")
        tracker.merge(
            ResultAnnotations(sensitivity=SimpleDataClass.PII),
            tool_name="patient_lookup",
        )
        summary = tracker.summary()
        assert "s1" in summary
        assert "patient_lookup" in summary
        assert "pii" in summary.lower() or "PII" in summary

    def test_reset_blocked_by_default(self):
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.CREDENTIALS))
        with pytest.raises(RuntimeError, match="reset\\(\\) is disabled"):
            tracker.reset()

    def test_reset_allowed_when_opted_in(self):
        tracker = SessionTracker(allow_reset=True)
        tracker.merge(ResultAnnotations(
            sensitivity=SimpleDataClass.CREDENTIALS,
            open_world_hint=True,
        ))
        tracker.reset()
        assert tracker.call_count == 0
        assert tracker.has_seen_sensitive_data() is False
        assert tracker.session.open_world_hint is False

    def test_call_count(self):
        tracker = SessionTracker()
        for i in range(5):
            tracker.merge(ResultAnnotations())
        assert tracker.call_count == 5

    def test_session_returns_snapshot_not_reference(self):
        """Mutations on the returned session must not affect the tracker."""
        tracker = SessionTracker()
        tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        snapshot = tracker.session
        # Mutate the snapshot
        snapshot.max_sensitivity = SimpleDataClass.NONE
        snapshot.open_world_hint = True
        snapshot.attribution.add("injected")
        # Tracker state must be unchanged
        assert tracker.session.max_sensitivity == SimpleDataClass.PII
        assert tracker.session.open_world_hint is False
        assert "injected" not in tracker.session.attribution
