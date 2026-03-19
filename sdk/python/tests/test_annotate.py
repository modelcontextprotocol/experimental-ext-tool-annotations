"""Tests for mcp_trust.annotate — decorator and wire-format serialization."""

import asyncio
import pytest
from trust_types import (
    Destination,
    InputMetadata,
    Outcome,
    Regulated,
    ReturnMetadata,
    SimpleDataClass,
    Source,
    TrustAnnotations,
)
from annotate import (
    from_wire,
    get_trust_annotations,
    is_trust_annotated,
    to_wire,
    trust_annotated,
)


# ---------------------------------------------------------------------------
# Decorator basics
# ---------------------------------------------------------------------------

class TestDecorator:
    def test_sync_function_preserves_behavior(self):
        @trust_annotated(attribution=("test",))
        def greet(name: str) -> str:
            return f"Hello, {name}"

        assert greet("World") == "Hello, World"

    def test_async_function_preserves_behavior(self):
        @trust_annotated(attribution=("test",))
        async def greet(name: str) -> str:
            return f"Hello, {name}"

        result = asyncio.get_event_loop().run_until_complete(greet("World"))
        assert result == "Hello, World"

    def test_annotations_attached(self):
        @trust_annotated(
            malicious_activity_hint=True,
            attribution=("EHR",),
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.PII,
            ),
        )
        def patient_lookup(pid: str) -> dict:
            return {}

        ann = get_trust_annotations(patient_lookup)
        assert ann is not None
        assert ann.malicious_activity_hint is True
        assert ann.attribution == ("EHR",)
        assert ann.return_metadata.source == Source.INTERNAL
        assert ann.return_metadata.sensitivity == SimpleDataClass.PII

    def test_is_trust_annotated(self):
        @trust_annotated()
        def foo():
            pass

        def bar():
            pass

        assert is_trust_annotated(foo) is True
        assert is_trust_annotated(bar) is False

    def test_unannotated_returns_none(self):
        def plain():
            pass

        assert get_trust_annotations(plain) is None

    def test_preserves_name_and_docstring(self):
        @trust_annotated()
        def my_tool():
            """My docstring."""
            pass

        assert my_tool.__name__ == "my_tool"
        assert my_tool.__doc__ == "My docstring."

    def test_exception_propagation(self):
        @trust_annotated()
        def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            failing()


# ---------------------------------------------------------------------------
# Wire-format serialization
# ---------------------------------------------------------------------------

class TestToWire:
    def test_empty_annotations(self):
        ta = TrustAnnotations()
        assert to_wire(ta) == {}

    def test_malicious_hint(self):
        ta = TrustAnnotations(malicious_activity_hint=True)
        assert to_wire(ta) == {"maliciousActivityHint": True}

    def test_attribution(self):
        ta = TrustAnnotations(attribution=("EHR", "Billing"))
        wire = to_wire(ta)
        assert wire == {"attribution": ["EHR", "Billing"]}

    def test_return_metadata_simple(self):
        ta = TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.PII,
            )
        )
        wire = to_wire(ta)
        assert wire == {
            "returnMetadata": {
                "source": "internal",
                "sensitivity": "pii",
            }
        }

    def test_return_metadata_regulated(self):
        ta = TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA", "SOX"),
            )
        )
        wire = to_wire(ta)
        assert wire["returnMetadata"]["sensitivity"] == {
            "regulated": {"scopes": ["HIPAA", "SOX"]}
        }

    def test_input_metadata_simple(self):
        ta = TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.IRREVERSIBLE,
            )
        )
        wire = to_wire(ta)
        assert wire == {
            "inputMetadata": {
                "destination": "public",
                "sensitivity": "none",
                "outcomes": "irreversible",
            }
        }

    def test_input_metadata_arrays(self):
        ta = TrustAnnotations(
            input_metadata=InputMetadata(
                destination=(Destination.INTERNAL, Destination.PUBLIC),
                sensitivity=(SimpleDataClass.PII, SimpleDataClass.FINANCIAL),
                outcomes=(Outcome.CONSEQUENTIAL, Outcome.IRREVERSIBLE),
            )
        )
        wire = to_wire(ta)
        im = wire["inputMetadata"]
        assert im["destination"] == ["internal", "public"]
        assert im["sensitivity"] == ["pii", "financial"]
        assert im["outcomes"] == ["consequential", "irreversible"]

    def test_full_annotations(self):
        ta = TrustAnnotations(
            malicious_activity_hint=False,
            attribution=("EHR-v3",),
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.PII,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
        )
        wire = to_wire(ta)
        assert "maliciousActivityHint" in wire
        assert "attribution" in wire
        assert "inputMetadata" in wire
        assert "returnMetadata" in wire


# ---------------------------------------------------------------------------
# Wire-format deserialization
# ---------------------------------------------------------------------------

class TestFromWire:
    def test_empty(self):
        ta = from_wire({})
        assert ta == TrustAnnotations()

    def test_simple_sensitivity(self):
        ta = from_wire({
            "returnMetadata": {
                "source": "internal",
                "sensitivity": "pii",
            }
        })
        assert ta.return_metadata is not None
        assert ta.return_metadata.source == Source.INTERNAL
        assert ta.return_metadata.sensitivity == SimpleDataClass.PII

    def test_regulated_sensitivity(self):
        ta = from_wire({
            "returnMetadata": {
                "source": "system",
                "sensitivity": {"regulated": {"scopes": ["HIPAA"]}},
            }
        })
        assert isinstance(ta.return_metadata.sensitivity, Regulated)
        assert ta.return_metadata.sensitivity.regulated.scopes == ("HIPAA",)

    def test_roundtrip(self):
        original = TrustAnnotations(
            malicious_activity_hint=True,
            attribution=("EHR",),
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.FINANCIAL,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("PCI-DSS"),
            ),
        )
        wire = to_wire(original)
        restored = from_wire(wire)

        assert restored.malicious_activity_hint == original.malicious_activity_hint
        assert restored.attribution == original.attribution
        assert restored.input_metadata.destination == original.input_metadata.destination
        assert restored.return_metadata.sensitivity == original.return_metadata.sensitivity


# ---------------------------------------------------------------------------
# Wire-format validation
# ---------------------------------------------------------------------------

class TestFromWireValidation:
    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="expects a dict"):
            from_wire("not a dict")

    def test_rejects_non_bool_malicious_hint(self):
        with pytest.raises(ValueError, match="maliciousActivityHint must be bool"):
            from_wire({"maliciousActivityHint": "yes"})

    def test_rejects_non_array_attribution(self):
        with pytest.raises(ValueError, match="attribution must be an array"):
            from_wire({"attribution": "not-an-array"})

    def test_rejects_non_string_attribution_items(self):
        with pytest.raises(ValueError, match="attribution\\[1\\] must be a string"):
            from_wire({"attribution": ["ok", 42]})

    def test_rejects_unknown_sensitivity_value(self):
        with pytest.raises(ValueError, match="Unknown sensitivity value"):
            from_wire({"returnMetadata": {"sensitivity": "top_secret"}})

    def test_rejects_malformed_regulated_no_scopes(self):
        with pytest.raises(ValueError, match="regulated must be an object with 'scopes'"):
            from_wire({"returnMetadata": {"sensitivity": {"regulated": "bad"}}})

    def test_rejects_non_array_regulated_scopes(self):
        with pytest.raises(ValueError, match="regulated.scopes must be an array"):
            from_wire({"returnMetadata": {"sensitivity": {"regulated": {"scopes": "HIPAA"}}}})

    def test_rejects_non_string_scope_items(self):
        with pytest.raises(ValueError, match="regulated.scopes\\[0\\] must be a string"):
            from_wire({"returnMetadata": {"sensitivity": {"regulated": {"scopes": [123]}}}})
