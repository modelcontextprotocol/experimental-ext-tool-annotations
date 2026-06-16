#!/usr/bin/env python3
"""Worked emitter/consumer cases for the MCP `io.modelcontextprotocol/trust-annotations` extension
(experimental-ext-tool-annotations PR #2), expressed entirely in that extension's own vocabulary.

Two families the maintainer asked for to validate the shape:

  A. Emitter classification — a *public* repo that serves a *private* subresource. Visibility is a
     per-resource property, not a per-repo one, so the emitter classifies the resource it returns,
     not the container. The wire signal is the coarse `sensitive` boolean; the richer four-level
     class rides an out-of-band `evidenceRef` of `type: "data-class.v1"`. Unknown / mixed provenance
     classifies `sensitive: true` (conservative), never defaulted to public from a repo-level
     shortcut. Content-block annotations use union semantics: a block may refine but MUST NOT weaken
     a result-level claim.

  B. `evidenceRef` re-derivation — `type: "policy-decision"` and `type: "sequence"`, the small
     annotation on the wire (type + digest + canonicalization) with the rich record out of band.
     A client holding the record re-derives the digest independently. Shown under BOTH
     `cbor/rfc8949` and `jcs/rfc8785` so neither canonicalization reads as the default; the same
     record under the two envelopes yields two distinct, each-recomputable digests.

Everything reproduces from the bytes in `examples.json` alone: this script recomputes every
`evidenceRef.digest` from the committed record under its declared `canonicalization` and asserts the
match, checks the per-resource classification rule, and checks content-block union semantics. No
third-party dependencies: a pure-Python JCS (RFC 8785) and a minimal canonical CBOR (RFC 8949
§4.2.1) encoder are used and self-tested against the RFC's own published vectors before any digest is
trusted.

Restricted value profile (matches the draft's "small record" intent): text strings, arrays, maps
with string keys, booleans, null, and non-negative integers. No floats / no RFC 8785 number-format
edge cases are exercised; a record outside the profile raises rather than hashing silently.

Usage:
  python3 worked_cases.py            # self-test, (re)generate examples.json, verify, print PASS
  python3 worked_cases.py --verify   # verify the committed examples.json only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, "examples.json")
EXT = "io.modelcontextprotocol/trust-annotations"


# --------------------------------------------------------------------------------------------------
# Canonicalization (restricted profile), stdlib-only.
# --------------------------------------------------------------------------------------------------
def _reject_unsupported(v) -> None:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return
    if isinstance(v, int):
        if v < 0:
            raise ValueError("restricted profile: non-negative integers only")
        return
    if isinstance(v, list):
        for x in v:
            _reject_unsupported(x)
        return
    if isinstance(v, dict):
        for k, val in v.items():
            if not isinstance(k, str):
                raise ValueError("restricted profile: object keys must be strings")
            _reject_unsupported(val)
        return
    raise ValueError(f"restricted profile: unsupported type {type(v).__name__}")


def jcs_bytes(record) -> bytes:
    """RFC 8785 JCS for the restricted profile: sorted keys, no whitespace, UTF-8. (Number-format
    canonicalization is not exercised because the profile excludes floats.)"""
    _reject_unsupported(record)
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _cbor_head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    if n < 0x100:
        return bytes([(major << 5) | 24, n])
    if n < 0x10000:
        return bytes([(major << 5) | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([(major << 5) | 26]) + n.to_bytes(4, "big")
    return bytes([(major << 5) | 27]) + n.to_bytes(8, "big")


def cbor_bytes(record) -> bytes:
    """RFC 8949 core-deterministic encoding for the restricted profile: definite lengths, smallest
    integer encoding, map keys sorted by their encoded bytes (§4.2.1)."""
    _reject_unsupported(record)

    def enc(v) -> bytes:
        if v is True:
            return b"\xf5"
        if v is False:
            return b"\xf4"
        if v is None:
            return b"\xf6"
        if isinstance(v, int):  # bool already handled above
            return _cbor_head(0, v)
        if isinstance(v, str):
            b = v.encode("utf-8")
            return _cbor_head(3, len(b)) + b
        if isinstance(v, list):
            return _cbor_head(4, len(v)) + b"".join(enc(x) for x in v)
        if isinstance(v, dict):
            pairs = sorted(((enc(k), enc(val)) for k, val in v.items()), key=lambda kv: kv[0])
            return _cbor_head(5, len(v)) + b"".join(k + val for k, val in pairs)
        raise ValueError(f"unsupported type {type(v).__name__}")

    return enc(record)


CANON = {"jcs/rfc8785": jcs_bytes, "cbor/rfc8949": cbor_bytes}


def compute_digest(record, canonicalization: str) -> str:
    enc = CANON.get(canonicalization)
    if enc is None:
        raise ValueError(f"unknown canonicalization {canonicalization!r}")
    return "sha256:" + hashlib.sha256(enc(record)).hexdigest()


# --------------------------------------------------------------------------------------------------
# Self-test the encoders against the RFCs' own vectors before trusting any digest.
# --------------------------------------------------------------------------------------------------
def self_test() -> None:
    # RFC 8949 Appendix A (the subset within our value profile).
    cbor_vectors = [
        (0, "00"), (1, "01"), (10, "0a"), (23, "17"), (24, "1818"), (25, "1819"),
        (100, "1864"), (1000, "1903e8"),
        (False, "f4"), (True, "f5"), (None, "f6"),
        ("", "60"), ("a", "6161"), ("IETF", "6449455446"),
        ([], "80"), ([1, 2, 3], "83010203"),
        ({}, "a0"),
        ({"a": 1, "b": [2, 3]}, "a26161016162820203"),
        ({"a": "A", "b": "B", "c": "C", "d": "D", "e": "E"},
         "a56161614161626142616361436164614461656145"),
    ]
    for value, expected_hex in cbor_vectors:
        got = cbor_bytes(value).hex()
        assert got == expected_hex, f"CBOR self-test failed for {value!r}: {got} != {expected_hex}"
    # CBOR canonical map-key ordering (§4.2.1): keys sorted by encoded bytes, shorter key first.
    # {"a":2,"b":1,"aa":3} -> a3 (6161 02)(6162 01)(626161 03).
    assert cbor_bytes({"b": 1, "a": 2, "aa": 3}).hex() == "a361610261620162616103"
    # JCS sorts keys, drops whitespace, keeps UTF-8.
    assert jcs_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert jcs_bytes({"name": "café"}) == '{"name":"café"}'.encode("utf-8")


# --------------------------------------------------------------------------------------------------
# Out-of-band records (what each evidenceRef.digest commits to).
# --------------------------------------------------------------------------------------------------
# A.1/A.3 — a public repo serving a non-public subresource: the rich four-level class lives here,
# the wire carries only `sensitive: true`.
REC_DRAFT_ADVISORY = {
    "class": "confidential",
    "origin": "open_world",
    "resource_kind": "security_advisory_draft",
    "container_visibility": "public",
}
REC_COLLABORATOR_ROSTER = {
    "class": "confidential",
    "origin": "first_party",
    "resource_kind": "collaborator_roster",
    "container_visibility": "public",
}
# A.2 — a world-readable resource from the same public repo.
REC_PUBLIC_README = {
    "class": "public",
    "origin": "open_world",
    "resource_kind": "readme",
    "container_visibility": "public",
}
# A.4 — provenance not established at emit time: classify sensitive, do not default to public.
REC_UNKNOWN = {
    "class": "unknown",
    "origin": "unestablished",
    "resource_kind": "mixed",
}
# B.1 — a policy decision recorded out of band.
REC_POLICY_DECISION = {
    "decision": "deny",
    "rule": "egress.block_unverified_sink",
    "subject": "tool:web.fetch",
    "stage": "pre_call",
    "reasons": ["sink_not_in_allowlist", "input_marked_untrusted"],
}
# B.2 — a tool-call sequence shape recorded out of band.
REC_SEQUENCE = {
    "sequence": ["search", "open_document", "send_email"],
    "window": 3,
    "flagged_step": 2,
}


def evidence_ref(record, type_: str, canonicalization: str, *, schema=None, ref=None) -> dict:
    er = {
        "type": type_,
        "digest": compute_digest(record, canonicalization),
        "canonicalization": canonicalization,
    }
    if schema is not None:
        er["schema"] = schema
    if ref is not None:
        er["ref"] = ref
    return er


def build_cases() -> list[dict]:
    cases: list[dict] = []

    # ---- Family A: emitter classification (public repo, private subresource) ----
    cases.append({
        "id": "A1_public_repo_draft_advisory",
        "family": "emitter_classification",
        "narrative": "A public repository serves a draft security advisory. The repo is world-public; "
                     "the subresource is not. The emitter classifies the resource it returns, so the "
                     "result is sensitive even though the container is public.",
        "resource_visibility": "private",
        "wire": {"_meta": {EXT: {
            "sensitive": True,
            "evidenceRef": evidence_ref(REC_DRAFT_ADVISORY, "data-class.v1", "jcs/rfc8785",
                                        schema="https://example/data-class.v1.json"),
        }}},
        "record": REC_DRAFT_ADVISORY,
    })
    cases.append({
        "id": "A2_public_repo_readme",
        "family": "emitter_classification",
        "narrative": "The same public repository serves its README. World-readable, so no sensitive "
                     "claim is made (absence is 'no claim', never 'asserted false'). A data-class.v1 "
                     "record may still record class=public for downstream audit.",
        "resource_visibility": "public",
        "wire": {"_meta": {EXT: {
            "evidenceRef": evidence_ref(REC_PUBLIC_README, "data-class.v1", "jcs/rfc8785"),
        }}},
        "record": REC_PUBLIC_README,
    })
    cases.append({
        "id": "A3_public_repo_collaborator_roster",
        "family": "emitter_classification",
        "narrative": "The same public repository serves its collaborator roster: not world-readable, "
                     "so sensitive=true per-resource. Digest-only evidenceRef (no schema/ref) is still "
                     "a usable bounded signal and remains re-derivable.",
        "resource_visibility": "private",
        "wire": {"_meta": {EXT: {
            "sensitive": True,
            "evidenceRef": evidence_ref(REC_COLLABORATOR_ROSTER, "data-class.v1", "cbor/rfc8949"),
        }}},
        "record": REC_COLLABORATOR_ROSTER,
    })
    cases.append({
        "id": "A4_unknown_or_mixed_provenance",
        "family": "emitter_classification",
        "narrative": "Provenance is not established at emit time (mixed or unknown source). The emitter "
                     "classifies sensitive=true rather than defaulting to public from a repo-level "
                     "shortcut; the consumer treats it conservatively until provenance is established.",
        "resource_visibility": "unknown",
        "wire": {"_meta": {EXT: {
            "sensitive": True,
            "evidenceRef": evidence_ref(REC_UNKNOWN, "data-class.v1", "jcs/rfc8785"),
        }}},
        "record": REC_UNKNOWN,
    })
    cases.append({
        "id": "A5_content_block_union_no_weaken",
        "family": "emitter_classification",
        "narrative": "One search result among many is the private subresource. The CallToolResult makes "
                     "no result-level sensitive claim, but the offending ContentBlock sets sensitive=true. "
                     "Union semantics: the block refines and may only strengthen; effective sensitive=true.",
        "resource_visibility": "private",
        "wire": {
            "result_meta": {EXT: {}},
            "content_block_meta": {EXT: {
                "sensitive": True,
                "evidenceRef": evidence_ref(REC_DRAFT_ADVISORY, "data-class.v1", "jcs/rfc8785"),
            }},
        },
        "record": REC_DRAFT_ADVISORY,
        "effective_sensitive": True,
    })

    # ---- Family B: evidenceRef re-derivation (policy-decision, sequence; both canonicalizations) ----
    cases.append({
        "id": "B1_policy_decision_cbor",
        "family": "evidence_ref_rederivation",
        "narrative": "A policy decision kept out of band; the wire annotation carries only the small "
                     "evidenceRef. A client holding the decision record re-derives the digest under "
                     "cbor/rfc8949 and matches.",
        "wire": {"_meta": {EXT: {
            "evidenceRef": evidence_ref(REC_POLICY_DECISION, "policy-decision", "cbor/rfc8949",
                                        schema="https://example/policy-decision.v1.json",
                                        ref="audit://decisions/2026-06-16/0001"),
        }}},
        "record": REC_POLICY_DECISION,
    })
    cases.append({
        "id": "B2_sequence_jcs",
        "family": "evidence_ref_rederivation",
        "narrative": "A tool-call sequence shape kept out of band; the wire annotation carries only the "
                     "small evidenceRef. A client re-derives the digest under jcs/rfc8785 and matches.",
        "wire": {"_meta": {EXT: {
            "evidenceRef": evidence_ref(REC_SEQUENCE, "sequence", "jcs/rfc8785",
                                        schema="https://example/sequence.v1.json"),
        }}},
        "record": REC_SEQUENCE,
    })
    cases.append({
        "id": "B3_same_record_two_envelopes",
        "family": "evidence_ref_rederivation",
        "narrative": "The same data-class record under both canonicalizations yields two distinct, "
                     "each-recomputable digests — canonicalization is a per-reference envelope choice, "
                     "neither is the default.",
        "wire_cbor": {"_meta": {EXT: {
            "evidenceRef": evidence_ref(REC_DRAFT_ADVISORY, "data-class.v1", "cbor/rfc8949"),
        }}},
        "wire_jcs": {"_meta": {EXT: {
            "evidenceRef": evidence_ref(REC_DRAFT_ADVISORY, "data-class.v1", "jcs/rfc8785"),
        }}},
        "record": REC_DRAFT_ADVISORY,
    })
    return cases


# --------------------------------------------------------------------------------------------------
# Verification: recompute every digest from the record bytes, check classification + union semantics.
# --------------------------------------------------------------------------------------------------
def _all_evidence_refs(case: dict):
    """Yield (evidenceRef, wire_key) for every evidenceRef in a case's wire annotation(s)."""
    for key in ("wire", "wire_cbor", "wire_jcs"):
        wire = case.get(key)
        if not wire:
            continue
        for meta_holder in ("_meta", "result_meta", "content_block_meta"):
            meta = wire.get(meta_holder)
            if meta and EXT in meta and "evidenceRef" in meta[EXT]:
                yield meta[EXT]["evidenceRef"], key


def verify(cases: list[dict]) -> None:
    checked = 0
    for case in cases:
        # 1. Every evidenceRef digest re-derives from the record bytes under its canonicalization.
        for er, _ in _all_evidence_refs(case):
            recomputed = compute_digest(case["record"], er["canonicalization"])
            assert recomputed == er["digest"], (
                f"{case['id']}: digest mismatch under {er['canonicalization']}: "
                f"{recomputed} != {er['digest']}"
            )
            checked += 1

        # 2. B3: the two envelopes must produce DIFFERENT digests (distinct re-derivable references).
        if case["id"] == "B3_same_record_two_envelopes":
            d_cbor = case["wire_cbor"]["_meta"][EXT]["evidenceRef"]["digest"]
            d_jcs = case["wire_jcs"]["_meta"][EXT]["evidenceRef"]["digest"]
            assert d_cbor != d_jcs, "B3: the two canonicalizations should differ"

        # 3. Emitter classification rule (per-resource, fail-closed on unknown).
        if case["family"] == "emitter_classification":
            vis = case.get("resource_visibility")
            if case["id"] == "A5_content_block_union_no_weaken":
                result_claim = case["wire"]["result_meta"][EXT].get("sensitive")
                block_claim = case["wire"]["content_block_meta"][EXT].get("sensitive")
                effective = bool(result_claim) or bool(block_claim)  # union; once true stays true
                assert effective is True and case["effective_sensitive"] is True
                assert block_claim is True and not result_claim, "block must refine, not weaken"
            else:
                sensitive = case["wire"]["_meta"][EXT].get("sensitive")
                if vis in ("private", "unknown"):
                    assert sensitive is True, f"{case['id']}: {vis} resource must be sensitive=true"
                elif vis == "public":
                    assert sensitive is not True, f"{case['id']}: public resource must not claim sensitive"
    print(f"verified {checked} evidenceRef digests across {len(cases)} cases", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="verify committed examples.json only")
    args = ap.parse_args()

    self_test()  # encoders match the RFC vectors before any digest is trusted

    if args.verify:
        with open(EXAMPLES, encoding="utf-8") as fh:
            doc = json.load(fh)
        cases = doc["cases"]
    else:
        cases = build_cases()
        doc = {
            "extension": EXT,
            "summary": "worked emitter/consumer cases: public-repo private-subresource classification "
                       "+ policy-decision / sequence evidenceRef re-derivation, reproducible from bytes",
            "canonicalizations": ["cbor/rfc8949", "jcs/rfc8785"],
            "value_profile": "text strings, arrays, string-keyed maps, booleans, null, non-negative "
                             "integers (no floats / RFC 8785 number edge cases)",
            "cases": cases,
        }
        with open(EXAMPLES, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
            fh.write("\n")

    verify(cases)
    print("PASS")


if __name__ == "__main__":
    main()
