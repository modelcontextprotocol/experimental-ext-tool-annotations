---
title: Derivation lineage (data-labelling scheme)
---

> ⚠️ **Experimental scheme skeleton.** This is one **data-labelling scheme** that
> fills the [`trust-annotations`](../specification/draft/trust-annotations.mdx)
> `evidenceRef` slot via `type: "lineage.derivation.v1"`. It is **not** an MCP
> extension and **not** a sibling of the extensions, and it does **not** add
> propagation rules to `trust-annotations`. See
> [Why a scheme](#why-a-scheme-not-a-wire-field).

**Scheme** — fills `trust-annotations`'s `evidenceRef` slot, selected by
`evidenceRef.type == "lineage.derivation.v1"`. Not an extension.

## Abstract

This scheme defines `lineage.derivation.v1`, an entry for the `trust-annotations`
`evidenceRef` slot that carries **per-result derivation lineage**: which source
results or stored items a result was derived from, and what those sources were
labelled at derivation time. A host that implements the scheme can keep a
source's sensitivity and access constraints attached to anything derived from
it — a summary, an aggregate, an embedding — across a write to storage and a
later read. It is a candidate path for the parked
[taint persistence across the store boundary](../docs/open-questions.md#parked-sep-1913-umbrella)
item. The model follows *Lineage-Aware Memory Governance*
([doi:10.1109/ACCESS.2026.3730363](https://doi.org/10.1109/ACCESS.2026.3730363)).

## Why a scheme, not a wire field

The [decision log](../docs/decisions.md) (2026-06-10) parked propagation rules on
the SEP-1913 umbrella, and `trust-annotations` § Propagation says the extension
does not specify them; a host MAY implement propagation locally. This scheme
respects that boundary. It standardizes no propagation rule for the extension.
It only defines a record a producer can attach so that a host which *chooses* to
enforce taint persistence has the evidence to do so after a store round-trip.

The wire floor is unchanged. Per the "emit both" guidance, a producer of this
scheme still emits the coarse `sensitive` boolean; the lineage record refines it
for hosts that implement the scheme and is ignorable by those that don't.

## Motivation

[@JustinCappos](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2967516811)
gave the basic case: write a card number to a file, read it back, and the
sensitivity label must not silently disappear. Agent memory makes the case
harder, because what is written back is usually *derived* rather than copied:

1. A tool returns a result marked `sensitive: true`.
2. The agent summarizes it, aggregates it with other results, or embeds it.
3. The derived item is written to memory or a store.
4. Later — possibly in another session, for another principal — a read returns
   the derived item with no label, or with a label computed only from its own
   content.

Content filtering cannot catch step 4: a summary or an aggregate may contain no
sensitive tokens at all while still disclosing what its source was about. A
label stamped once at write time has a second problem: it goes stale. If the
source is later reclassified, or the reader's access to it is revoked, a
write-time label on the derivative does not change. What the host needs is the
derivative's **ancestry**, so it can re-check the reader against the sources at
read time.

## Specification

### Scheme identity

A `lineage.derivation.v1` record is selected by
`evidenceRef.type == "lineage.derivation.v1"` on a `trust-annotations`
annotation. The `digest`/`canonicalization` pair over the record is required
exactly as for any other scheme. A client that does not implement the scheme
MUST be able to ignore it safely.

### Payload (skeleton)

The record is a JSON object. Shapes below are candidates, not settled:

```jsonc
{
  "operation": "summary",
  "lineageComplete": true,
  "derivedAt": "2026-11-26T14:03:00Z",
  "derivedFrom": [
    {
      "ref": "urn:example:result:7f3c",          // opaque, host-resolved
      "sensitive": true,                           // ancestor's wire value at derivation time
      "digest": "sha256:…",                        // ancestor's own evidenceRef.digest, copied verbatim
      "authorityRef": "urn:example:acl:crm-q3",    // optional, opaque, host-resolved
      "evidenceRef": {                             // optional, ancestor's scheme record
        "type": "data-class.v1",
        "digest": "sha256:…",
        "canonicalization": "jcs/rfc8785"
      }
    },
    { "ref": "urn:example:result:91aa", "sensitive": false }
  ]
}
```

| Field | Required | Meaning |
| :--- | :--- | :--- |
| `derivedFrom` | yes | Array of ancestor entries, one per input the producer used. MAY be empty only for an original (non-derived) item. |
| `derivedFrom[].ref` | yes | Opaque locator for the ancestor result or stored item. Meaningful only to the host or store that issued it. |
| `derivedFrom[].sensitive` | yes | The ancestor's `trust-annotations` `sensitive` value at derivation time (`false` when absent on the ancestor). |
| `derivedFrom[].digest` | optional | The ancestor's own `evidenceRef.digest`, copied verbatim, so a host can detect that the ancestor's evidence has since changed. |
| `derivedFrom[].authorityRef` | optional | Opaque reference to the access policy or entitlement that governed the ancestor. Resolved host-side; see [Authority resolution](#authority-resolution). |
| `derivedFrom[].evidenceRef` | optional | The ancestor's scheme record pointer, in the `trust-annotations` `evidenceRef` shape (e.g. a `data-class.v1` record). |
| `operation` | recommended | Open string naming how the result was derived. Suggested values: `copy`, `summary`, `aggregate`, `embedding`, `transform`. Not an enum. |
| `lineageComplete` | yes | `true` only if every input the producer used is listed. `false` when the producer knows some inputs were not recorded or were truncated. |
| `derivedAt` | recommended | [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) timestamp of the derivation. |

An ancestor can itself carry a `lineage.derivation.v1` record, so lineage is a
graph a host can walk. Whether the record should inline transitive ancestors is
an [open question](#open-questions).

### Authority resolution

`ref` and `authorityRef` are **opaque on the wire and resolved host-side**, in
the same way the [FIDES scheme](./ifc-fides.md#reader-set-resolution) treats a
`"private"` reader set. The record never carries reader identities or ACL
contents. At decision time the host maps each `authorityRef` (or, absent one,
each `ref`) to the current access policy using its own credentials, evaluates the
reader against it, and discards the resolved policy. A host SHOULD NOT cache a
resolved policy as a durable grant.

### Producer requirements

These are the scheme's emission rules, not propagation rules for the extension.

- A producer that writes a derived item MUST list every input it used in
  `derivedFrom`. If it cannot, it MUST set `lineageComplete: false`.
- A producer SHOULD set the wire `sensitive: true` on the derived item when any
  ancestor had `sensitive: true`, and MUST NOT omit `sensitive` merely because
  this record is present.
- A producer MUST NOT drop an ancestor because the derived content no longer
  appears to contain anything from it.

### Consumer guidance

A host that implements the scheme:

- SHOULD, at **read time**, evaluate the reader's authority against every
  resolvable ancestor, not only against the derived item.
- SHOULD fail closed — deny, redact, or prompt — when `lineageComplete` is
  `false` or an ancestor cannot be resolved, if its policy requires complete
  lineage. A host whose policy does not require it MAY fall back to the wire
  `sensitive` floor.
- Treats a change of authority on an ancestor (revocation, reclassification) as
  applying to its derivatives on the **next read**. This is the property a
  write-time label cannot provide.
- Distinguishes **deleting** an ancestor from **changing its authority**. An
  authority change is evaluated as above. Deletion semantics (whether a
  derivative of a deleted ancestor remains readable, must be purged, or is
  treated as unresolvable) are **host-defined** and out of scope here; retention
  and erasure are the subject of
  [issue #6](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/issues/6).

### Interaction with other schemes

- **`data-class.v1`** — an ancestor's classification travels as the nested
  `evidenceRef`, so a host can recompute the derived item's effective class
  (e.g. the most restrictive ancestor class) after a store round-trip.
- **`ifc.fides.v1`** — FIDES joins labels when data is combined. This scheme
  records *which* inputs were combined, so the join can be recomputed after the
  result has left the session and come back from storage, including the
  host-resolved `private ⊔ private` intersection.
- **Attestation envelopes** (in-toto, SEP-2787) — an envelope could sign a
  `lineage.derivation.v1` record; this scheme says what was derived from what,
  an attestation says who vouches for it.

### Graceful degradation

A client that does not implement `lineage.derivation.v1` ignores the record and
relies on the `sensitive` floor, which a conforming producer still sets when any
ancestor was sensitive. The limitation is real: without the scheme, a later
revocation or reclassification of an ancestor is **not** visible, and a client
sees only the label as it stood at write time.

## Producer / consumer

- **Producer (candidate).** A memory store or agent framework that records
  derivation edges at write time: when an item is produced from one or more tool
  results or stored items, it records their refs and labels alongside the item.
- **Consumer (candidate).** A host or memory-retrieval layer that re-checks the
  reader's authority against an item's ancestors at read time.
  [`amu-governance`](https://github.com/sangaraju1988/amu-governance) (MIT,
  [PyPI](https://pypi.org/project/amu-governance/)) implements a lineage-gated
  retrieval check of this kind for cached analytical results. It is not an MCP
  component and does not consume `lineage.derivation.v1` records today; mapping
  its lineage model onto this payload is the proof point for the consumer side.

## Security considerations

- **A lineage record is a claim.** A producer can omit ancestors or mislabel
  them. See [docs/trust-model.md](../docs/trust-model.md): `digest` makes the
  record checkable, not true.
- **Lineage can leak.** Ancestor refs, labels, and even the number of ancestors
  can disclose information about sources the reader may not see. A consumer
  MUST NOT return ancestor refs, labels, or counts to a reader who is denied
  access to the derived item or to any of its ancestors.
- **Size.** Lineage graphs can grow large. A producer MAY cap the depth or
  number of recorded ancestors and MUST set `lineageComplete: false` when it
  does.

## Open questions

- **Transitive depth.** Should a record list only direct parents, or inline
  ancestors to some depth? Direct parents keep records small but require the
  host to walk the graph.
- **Deletion vs. authority change.** Is host-defined deletion enough, or should
  the scheme coordinate with a lifecycle scheme from issue #6?
- **Locating the store.** Does `ref` need a standard shape (cf. the FIDES open
  question on `evidenceRef.ref`) so a host can find the originating store?
- **Size bounds.** Is a recommended cap on `derivedFrom` length useful, or
  should bounds be left to deployments?

## References

- V. Sangaraju and S. Vissa, "Lineage-Aware Memory Governance," *IEEE Access*,
  vol. 14, pp. 139683–139693, 2026,
  [doi:10.1109/ACCESS.2026.3730363](https://doi.org/10.1109/ACCESS.2026.3730363).
- FIDES — information-flow control for LLM agents,
  [arXiv:2505.23643](https://arxiv.org/abs/2505.23643).
- Permissive Information-Flow Analysis for LLMs,
  [arXiv:2410.03055](https://arxiv.org/abs/2410.03055).
- @JustinCappos on taint persistence across storage,
  [modelcontextprotocol#711](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2967516811).

## Changelog

| Date       | Change                                                       |
| ---------- | ------------------------------------------------------------ |
| 2026-11-26 | Initial draft skeleton. Payload shapes are candidates pending the open questions above. |
