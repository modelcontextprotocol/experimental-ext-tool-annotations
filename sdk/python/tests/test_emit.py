"""Tests for mcp_trust.emit — structured audit logging."""

import json
from trust_types import (
    ReturnMetadata,
    SimpleDataClass,
    Source,
    TrustAnnotations,
)
from emit import disable_logging, enable_logging


class TestEmitLogging:
    def test_enable_disable_cycle(self):
        """Logging can be enabled and disabled without error."""
        events = []
        enable_logging(callback=lambda e: events.append(e))
        disable_logging()
        assert events == []

    def test_callback_receives_events(self):
        events = []
        enable_logging(callback=lambda e: events.append(e))
        try:
            from emit import _emit_call, _emit_result
            ann = TrustAnnotations(attribution=("test",))
            _emit_call("my_tool", ann)
            _emit_result("my_tool", ann, 42.5, "ok")
            assert len(events) == 2
            assert events[0]["event"] == "tool.call"
            assert events[0]["tool"] == "my_tool"
            assert events[1]["event"] == "tool.result"
            assert events[1]["duration_ms"] == 42.5
        finally:
            disable_logging()

    def test_agent_id_in_events(self):
        events = []
        enable_logging(callback=lambda e: events.append(e), agent_id="urn:agent:test")
        try:
            from emit import _emit_call
            _emit_call("tool", TrustAnnotations())
            assert events[0]["agent"] == "urn:agent:test"
        finally:
            disable_logging()

    def test_no_events_when_disabled(self):
        disable_logging()
        from emit import _emit_call
        # Should not raise
        _emit_call("tool", TrustAnnotations())

    def test_stream_output(self):
        import io
        buf = io.StringIO()
        enable_logging(stream=buf)
        try:
            from emit import _emit_call
            _emit_call("my_tool", TrustAnnotations())
            output = buf.getvalue()
            parsed = json.loads(output.strip())
            assert parsed["event"] == "tool.call"
            assert parsed["tool"] == "my_tool"
        finally:
            disable_logging()

    def test_policy_event(self):
        events = []
        enable_logging(callback=lambda e: events.append(e))
        try:
            from emit import _emit_policy
            _emit_policy("tool", "block", "test reason", rule="test-rule")
            assert len(events) == 1
            assert events[0]["event"] == "policy.decision"
            assert events[0]["effect"] == "block"
            assert events[0]["rule"] == "test-rule"
        finally:
            disable_logging()
