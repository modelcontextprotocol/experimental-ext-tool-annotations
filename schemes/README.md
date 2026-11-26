# Data-labelling schemes

A **scheme** is a concrete data-labelling or tool-annotation approach that fills
the [`trust-annotations`](../specification/draft/trust-annotations.mdx)
`evidenceRef` slot under an `evidenceRef.type` value. The extension defines a
small, stable wire vocabulary and an open `type` pointer; a scheme defines the
richer, out-of-band record that pointer resolves to. The wire vocabulary (notably
`sensitive`) is a lowest-common-denominator floor every client can act on;
schemes refine it for hosts that implement them, and a server that can classify
more precisely is encouraged to emit **both** the floor and a scheme record.

Schemes are **not** extensions and **not** siblings of the extensions. They are
interchangeable: a deployment can adopt one, several, or none, and can swap them
without changing the extension. Modelling each labelling approach as a scheme keeps
any single academic model out of the wire root, which is the reason FIDES lives
here rather than as a top-level extension.

## Schemes here

| Scheme | `evidenceRef.type` | Status | Source |
| :--- | :--- | :--- | :--- |
| [FIDES information-flow control](./ifc-fides.md) | `ifc.fides.v1` | Draft skeleton | [arXiv:2505.23643](https://arxiv.org/abs/2505.23643) |
| [Data classification](./data-class.md) | `data-class.v1` | Draft skeleton | SEP-1913 taxonomy (`class` + regulatory scope) |
| [Derivation lineage](./lineage-derivation.md) | `lineage.derivation.v1` | Draft skeleton | [doi:10.1109/ACCESS.2026.3730363](https://doi.org/10.1109/ACCESS.2026.3730363) |

## Candidate schemes (not yet drafted)

The open `type` slot is designed to carry the range of models raised in the
[SEP-1913](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913)
review and the surrounding literature. Each is a candidate for its own scheme doc.
A scheme produces a **per-result data label** a server attaches:

| Approach | Likely `type` | Source |
| :--- | :--- | :--- |
| Permissive information-flow labels (influence-based propagation) | `ifc.permissive.v1` | [arXiv:2410.03055](https://arxiv.org/abs/2410.03055) |
| Contextual-integrity classification (per-task minimisation) | `ci.airgap.v1` | [arXiv:2405.05175](https://arxiv.org/abs/2405.05175) |
| ShardGuard | — | cited in SEP-1913 |
| Capability-token constraints (SINT) | — | SEP-1913 review thread |
| Caller/tool cosigning | — | SEP-1913 review thread |
| Sequence-shape audit records | — | SEP-1913 review thread |
| Tool-call attestation (in-toto / OVERT envelopes) | — | [SEP-2787](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2787), in-toto, OVERT |

These are leads, not commitments. A candidate becomes a scheme when someone
drafts it to the bar below; until then the slot simply stays open for it.

## Not schemes: host architectures

Some models raised in the same discussion are **host/client control-flow
architectures**, not data labels — they decide what to *do* with information,
they don't produce a per-result record a server attaches. They are prior art (see
[`related-work.md`](../docs/related-work.md)), not entries here:

| Approach | Why it isn't a scheme | Source |
| :--- | :--- | :--- |
| CaMeL (capability-based control/data-flow) | A host runtime; a capability token it issues *could* be referenced via `evidenceRef`, but the architecture isn't a label | [arXiv:2503.18813](https://arxiv.org/abs/2503.18813) |
| Design-pattern controls (Plan-Then-Execute, Dual LLM, Map-Reduce) | Client-side execution patterns, nothing on the wire | [arXiv:2506.08837](https://arxiv.org/abs/2506.08837) |

## Bar for adding a scheme

A scheme doc should state:

1. **Identity** — the `evidenceRef.type` value it claims, and that it is selected
   by `evidenceRef.type == "<value>"` on a `trust-annotations` annotation.
2. **Payload** — the shape of the record the `evidenceRef` resolves to.
3. **Graceful degradation** — how a client that does not implement the scheme
   ignores it safely (the `trust-annotations` booleans and
   `digest`/`canonicalization` pair remain meaningful regardless).
4. **Producer/consumer** — at least a candidate emitter and consumer, so the
   scheme is validated against real implementations rather than asserted.

`type` values are coordinated through the non-binding `evidenceRef.type` registry
noted in [`trust-annotations`](../specification/draft/trust-annotations.mdx) so
they don't collide.
