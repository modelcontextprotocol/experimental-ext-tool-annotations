"""Tests for mcp_trust.types — SEP-1913 type definitions."""

import pytest
from trust_types import (
    DataClass,
    Destination,
    InputMetadata,
    Outcome,
    Regulated,
    RegulatoryScope,
    ResultAnnotations,
    ReturnMetadata,
    SessionAnnotations,
    SimpleDataClass,
    Source,
    TrustAnnotations,
    max_sensitivity,
    sensitivity_level,
)


# ---------------------------------------------------------------------------
# Enum values match SEP-1913 wire format
# ---------------------------------------------------------------------------

class TestEnumValues:
    def test_destination_values(self):
        assert Destination.EPHEMERAL.value == "ephemeral"
        assert Destination.SYSTEM.value == "system"
        assert Destination.USER.value == "user"
        assert Destination.INTERNAL.value == "internal"
        assert Destination.PUBLIC.value == "public"

    def test_source_values(self):
        assert Source.UNTRUSTED_PUBLIC.value == "untrustedPublic"
        assert Source.TRUSTED_PUBLIC.value == "trustedPublic"
        assert Source.INTERNAL.value == "internal"
        assert Source.USER.value == "user"
        assert Source.SYSTEM.value == "system"

    def test_outcome_values(self):
        assert Outcome.BENIGN.value == "benign"
        assert Outcome.CONSEQUENTIAL.value == "consequential"
        assert Outcome.IRREVERSIBLE.value == "irreversible"

    def test_simple_data_class_values(self):
        assert SimpleDataClass.NONE.value == "none"
        assert SimpleDataClass.USER.value == "user"
        assert SimpleDataClass.PII.value == "pii"
        assert SimpleDataClass.FINANCIAL.value == "financial"
        assert SimpleDataClass.CREDENTIALS.value == "credentials"


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_regulatory_scope_frozen(self):
        rs = RegulatoryScope(("HIPAA",))
        with pytest.raises(AttributeError):
            rs.scopes = ("GDPR",)  # type: ignore

    def test_regulated_frozen(self):
        r = Regulated.of("HIPAA")
        with pytest.raises(AttributeError):
            r.regulated = RegulatoryScope(("GDPR",))  # type: ignore

    def test_input_metadata_frozen(self):
        im = InputMetadata()
        with pytest.raises(AttributeError):
            im.destination = Destination.PUBLIC  # type: ignore

    def test_return_metadata_frozen(self):
        rm = ReturnMetadata()
        with pytest.raises(AttributeError):
            rm.source = Source.UNTRUSTED_PUBLIC  # type: ignore

    def test_trust_annotations_frozen(self):
        ta = TrustAnnotations()
        with pytest.raises(AttributeError):
            ta.malicious_activity_hint = True  # type: ignore

    def test_result_annotations_frozen(self):
        ra = ResultAnnotations()
        with pytest.raises(AttributeError):
            ra.open_world_hint = True  # type: ignore


# ---------------------------------------------------------------------------
# Regulated convenience constructor
# ---------------------------------------------------------------------------

class TestRegulated:
    def test_of_single_scope(self):
        r = Regulated.of("HIPAA")
        assert r.regulated.scopes == ("HIPAA",)

    def test_of_multiple_scopes(self):
        r = Regulated.of("HIPAA", "SOX", "GDPR")
        assert r.regulated.scopes == ("HIPAA", "SOX", "GDPR")

    def test_empty_scope_raises(self):
        with pytest.raises(ValueError, match="at least one scope"):
            RegulatoryScope(())


# ---------------------------------------------------------------------------
# Sensitivity ordering
# ---------------------------------------------------------------------------

class TestSensitivityOrdering:
    def test_simple_ordering(self):
        levels = [sensitivity_level(dc) for dc in (
            SimpleDataClass.NONE,
            SimpleDataClass.USER,
            SimpleDataClass.PII,
            SimpleDataClass.FINANCIAL,
            SimpleDataClass.CREDENTIALS,
        )]
        assert levels == [0, 1, 2, 3, 4]

    def test_regulated_is_highest(self):
        assert sensitivity_level(Regulated.of("HIPAA")) == 5
        assert sensitivity_level(Regulated.of("HIPAA")) > sensitivity_level(SimpleDataClass.CREDENTIALS)

    def test_max_sensitivity_picks_higher(self):
        assert max_sensitivity(SimpleDataClass.NONE, SimpleDataClass.PII) == SimpleDataClass.PII
        assert max_sensitivity(SimpleDataClass.PII, SimpleDataClass.NONE) == SimpleDataClass.PII
        assert max_sensitivity(SimpleDataClass.CREDENTIALS, SimpleDataClass.USER) == SimpleDataClass.CREDENTIALS

    def test_max_sensitivity_regulated_wins(self):
        result = max_sensitivity(SimpleDataClass.CREDENTIALS, Regulated.of("HIPAA"))
        assert isinstance(result, Regulated)

    def test_max_sensitivity_merges_regulated_scopes(self):
        a = Regulated.of("HIPAA")
        b = Regulated.of("GDPR")
        result = max_sensitivity(a, b)
        assert isinstance(result, Regulated)
        assert set(result.regulated.scopes) == {"GDPR", "HIPAA"}


# ---------------------------------------------------------------------------
# SessionAnnotations propagation
# ---------------------------------------------------------------------------

class TestSessionAnnotations:
    def test_merge_open_world(self):
        session = SessionAnnotations()
        assert session.open_world_hint is False
        session.merge(ResultAnnotations(open_world_hint=True))
        assert session.open_world_hint is True
        # Once true, stays true
        session.merge(ResultAnnotations(open_world_hint=False))
        assert session.open_world_hint is True

    def test_merge_malicious(self):
        session = SessionAnnotations()
        session.merge(ResultAnnotations(malicious_activity_hint=True))
        assert session.malicious_activity_hint is True

    def test_merge_attribution(self):
        session = SessionAnnotations()
        session.merge(ResultAnnotations(attribution=("EHR",)))
        session.merge(ResultAnnotations(attribution=("Billing", "EHR")))
        assert session.attribution == {"EHR", "Billing"}

    def test_merge_sensitivity_escalation(self):
        session = SessionAnnotations()
        assert session.max_sensitivity == SimpleDataClass.NONE

        session.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        assert session.max_sensitivity == SimpleDataClass.PII

        # Can't de-escalate
        session.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE))
        assert session.max_sensitivity == SimpleDataClass.PII

        # Can escalate further
        session.merge(ResultAnnotations(sensitivity=SimpleDataClass.CREDENTIALS))
        assert session.max_sensitivity == SimpleDataClass.CREDENTIALS

    def test_merge_sensitivity_to_regulated(self):
        session = SessionAnnotations()
        session.merge(ResultAnnotations(sensitivity=SimpleDataClass.PII))
        session.merge(ResultAnnotations(sensitivity=Regulated.of("HIPAA")))
        assert isinstance(session.max_sensitivity, Regulated)
        assert session.max_sensitivity.regulated.scopes == ("HIPAA",)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_input_metadata_defaults(self):
        im = InputMetadata()
        assert im.destination == Destination.EPHEMERAL
        assert im.sensitivity == SimpleDataClass.NONE
        assert im.outcomes == Outcome.BENIGN

    def test_return_metadata_defaults(self):
        rm = ReturnMetadata()
        assert rm.source == Source.SYSTEM
        assert rm.sensitivity == SimpleDataClass.NONE

    def test_trust_annotations_defaults(self):
        ta = TrustAnnotations()
        assert ta.malicious_activity_hint is None
        assert ta.attribution == ()
        assert ta.input_metadata is None
        assert ta.return_metadata is None
