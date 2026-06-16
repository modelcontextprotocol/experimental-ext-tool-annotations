# MCP trust-annotations — worked emitter/consumer cases

Worked cases for the `io.modelcontextprotocol/trust-annotations` extension
([experimental-ext-tool-annotations PR #2](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/pull/2)),
built at the maintainer's request to validate the agreed shape. Expressed entirely in that
extension's own vocabulary (`sensitive` / `untrusted` booleans + `evidenceRef`
{type, digest, canonicalization, schema, ref}); no outside schema is introduced.

## What is covered

**A. Emitter classification — public repo, private subresource.** Visibility is per-resource, not
per-repo: a world-public repository still serves things that are not world-readable (a draft security
advisory, the collaborator roster). The emitter classifies the resource it returns. The wire carries
the coarse `sensitive` boolean; the four-level class rides an out-of-band `evidenceRef` of
`type: "data-class.v1"`. World-readable resources make no `sensitive` claim (absence is "no claim",
never "asserted false"). Unknown / mixed provenance classifies `sensitive: true`, never defaulted to
public from a repo-level shortcut. A content-block annotation may refine a result-level claim but
MUST NOT weaken it (union semantics: once `true`, stays `true`).

**B. `evidenceRef` re-derivation.** `type: "policy-decision"` and `type: "sequence"` — the small
annotation on the wire (type + digest + canonicalization) with the rich record out of band. A client
holding the record re-derives the digest independently. Shown under **both** `cbor/rfc8949` and
`jcs/rfc8785`; the same record under the two envelopes yields two distinct, each-recomputable digests,
so neither canonicalization reads as the default.

## Reproducing

```
python3 worked_cases.py            # self-test the encoders, (re)generate examples.json, verify
python3 worked_cases.py --verify   # verify the committed examples.json only
```

Everything reproduces from the bytes in `examples.json` alone. The script recomputes every
`evidenceRef.digest` from its committed record under the declared `canonicalization` and asserts the
match, checks the per-resource classification rule, and checks content-block union semantics.

No third-party dependencies: a pure-Python JCS (RFC 8785) and a minimal canonical CBOR (RFC 8949
§4.2.1) encoder, **self-tested against the RFCs' own published vectors** before any digest is trusted.

## Value profile (scope)

Text strings, arrays, string-keyed maps, booleans, null, and non-negative integers. Floats and the
RFC 8785 number-format edge cases are intentionally out of scope — a record outside the profile raises
rather than hashing silently. This matches the draft's "small record" intent; a production profile
that admits floats would pin number formatting explicitly, which is a separate question for the spec.
