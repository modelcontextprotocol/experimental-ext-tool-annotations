# Tool Annotations Interest Group — Experimental Extensions

> ⚠️ **Experimental** — This repository is an incubation space for the
> [Tool Annotations Interest Group](https://modelcontextprotocol.io/community/tool-annotations/charter).
> Contents are exploratory drafts intended to feed future Extensions Track SEPs
> ([SEP-2133](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2133)).
> They do not represent official MCP specifications or recommendations.

**Charter:** [modelcontextprotocol.io/community/tool-annotations/charter](https://modelcontextprotocol.io/community/tool-annotations/charter)
**Discord:** [#tool-annotations-ig](https://discord.com/channels/1358869848138059966/1482836798517543073)
**Open work:** [Pull requests](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/pulls)

## Why split the work?

[SEP-1913 (Trust and Sensitivity Annotations)](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913)
bundles four concerns that have proven hard to evaluate as a single unit: a
client-facing trust taxonomy, action-security metadata for tool I/O, a
malicious-activity signal, and propagation rules across session boundaries.

The sponsor, [@localden](https://github.com/localden), asked the central
question directly in review: the SEP "adds a few schema modifications and a
thorny array-or-scalar polymorphism on enum fields. If the taxonomy turns out
to be wrong, I worry that we can't remove it or easily modify it. Can we do a
potential narrower first cut?" The subsequent design discussion converged on a
layered answer: a small, stable annotation surface on the wire, with richer
evidence kept out-of-band and referenced by a bounded pointer.

This repo follows that steer. The schema-bearing concerns become **separate
experimental extensions**, each with its own [reverse-DNS identifier](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#definition),
reference implementation, and path to a future Extensions Track SEP, so drafts
can graduate independently. The concrete data-labelling models that fill an
extension's evidence slot are kept separate again — as interchangeable **schemes**
rather than extensions — so no single academic model is baked into the wire. This
directly addresses the "narrower first cut" ask without throwing away the
combinatoric value of the full set.

See [docs/decisions.md](docs/decisions.md) for the decision record and
[docs/trust-model.md](docs/trust-model.md) for the shared enforcement model.

## Extensions

| Identifier | Status | What it specifies | Reference implementation(s) |
| :--- | :--- | :--- | :--- |
| [`io.modelcontextprotocol/trust-annotations`](specification/draft/trust-annotations.mdx) | Draft skeleton | **Primary extension.** A small, scheme-agnostic client-facing data-classification vocabulary (`sensitive`, `untrusted`) on result `_meta`, plus an optional `evidenceRef` pointer slot that carries richer payloads out-of-band. | Python SDK: [`kapil8811/mcp-trust-annotations`](https://github.com/kapil8811/mcp-trust-annotations) (138-test suite, healthcare demo, LLM usability study). |
| [`io.modelcontextprotocol/action-metadata`](specification/draft/action-metadata.mdx) | Draft skeleton | `inputMetadata` / `returnMetadata` / outcome classifiers (incl. `requires_review`) on `ToolAnnotations`, describing where inputs go, where outputs originate, and what real-world effects a tool can cause. | Originally [SEP-2061 (Action Security Metadata)](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2061) by [@rreichel3](https://github.com/rreichel3) — closed 2026-06-13 in favour of this extension; worked example `read_drafts` / `list_inbox` / `send_email`. |
| [`io.modelcontextprotocol/display-templates`](specification/draft/display-templates.mdx) | Draft | Call-side display `template` on `Tool` `_meta` (branch-scoped inside `oneOf`/`anyOf` subschemas) and result-side server-rendered display `text` on content-block `_meta`: one legible line for the human watching, compact encodings for the model. Includes normative rendering semantics and a call-side omission indicator. | Python (stock SDK 2.x): [`maxiboch/soundboard`](https://github.com/maxiboch/soundboard) — mixer / cue transport / SFX-synth server plus a renderer implementing the normative substitution, branch-matching, and omission-indicator rules. |

Each extension is proposed in its own pull request so it can be reviewed and
graduate on its own clock.

## Data-labelling schemes (the `evidenceRef` slot)

The extensions above keep the wire vocabulary deliberately small. Richer
labelling lives **out-of-band**, referenced by the `trust-annotations`
[`evidenceRef`](specification/draft/trust-annotations.mdx) pointer, whose `type`
is an open string. A **scheme** is a concrete data-labelling or tool-annotation
approach that fills that slot under a `type` value. A scheme is **not** an
extension and not a sibling of the two above — it is one interchangeable way to
populate the evidence an extension carries, and a deployment can adopt, swap, or
ignore it without touching the extension.

The [`schemes/`](schemes/) folder collects these approaches. **FIDES** is the
first worked example, defining `ifc.fides.v1`; it is one model among several that
reviewers and the literature have raised, and the slot is designed so any of them
can occupy it:

| Scheme | `evidenceRef.type` | Source |
| :--- | :--- | :--- |
| FIDES information-flow control (integrity × confidentiality lattice) | `ifc.fides.v1` | [arXiv:2505.23643](https://arxiv.org/abs/2505.23643); emitter candidate [`github-mcp-server`](https://github.com/github/github-mcp-server) |
| Coarse data classification (4-level + regulatory scope) | `data-class.v1` | SEP-1913 taxonomy |
| Design-pattern controls (Plan-Then-Execute, Dual LLM, Map-Reduce) | _candidate_ | [arXiv:2506.08837](https://arxiv.org/abs/2506.08837) |
| Capability-token constraints (SINT) | _candidate_ | pshkv, [SEP-1913 thread](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913) |
| Caller/tool cosigning | _candidate_ | viftode4, SEP-1913 thread |
| Sequence-shape audit records | _candidate_ | marras0914, SEP-1913 thread |
| Tool-call attestation (in-toto / OVERT envelopes) | _candidate_ | [SEP-2787](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2787) |

Modelling IFC as a scheme rather than a namespace root is deliberate: a top-level
`ifc/` extension would bake one academic model into the wire and foreclose the
others. As one reviewer put it, IFC "fits relatively well if you use annotations"
— an endorsement of IFC *behind* the annotation slot, not as the slot itself. See
[`schemes/README.md`](schemes/README.md) for the full list and the bar for adding
a scheme.

## Relationship to SEP-1913

SEP-1913 remains the canonical place to discuss the overall problem framing.
This repository develops the schema-bearing parts of that proposal as
independently shippable extensions. When an extension here is ready to graduate,
an Extensions Track SEP can reference this repo as the prior art and the working
implementation that SEP-2133 [requires](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#creation).

For the full per-SEP plan — what happens to SEP-1913, SEP-2061, SEP-1862 and
others, and the SEP-2127 refactor precedent — see
[docs/sep-disposition.md](docs/sep-disposition.md).

**Out of scope for these extensions** (see [docs/open-questions.md](docs/open-questions.md)):

- **`maliciousActivityHint`** — reviewer concerns are structural (it fires at
  `tools/resolve` before execution can produce evidence; a boolean is the wrong
  granularity for client UX; clients won't trust server self-attestation). If it
  returns, it is per-`ContentBlock` with spans, on a different clock. It stays
  on the SEP-1913 umbrella rather than in an extension here.
- **Propagation rules** — sensitivity escalation across session boundaries, and
  the sequence-shape gap (an annotation surface for "this was call N in a
  flagged sequence") remain open. Likely a future extension once the taxonomy
  and `evidenceRef` shape are stable.

## Repository layout

This repo mirrors the structure of official extension repositories such as
[`ext-auth`](https://github.com/modelcontextprotocol/ext-auth):

```
specification/draft/<extension-name>.mdx   # one spec per extension (trust-annotations, action-metadata)
schemes/                                    # data-labelling schemes that fill the evidenceRef slot (FIDES, …)
docs/                                       # decision log, open questions, related work
MAINTAINERS.md                              # IG facilitators
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Substantive design discussion happens
on PRs against the relevant `specification/draft/*.mdx` file, in the IG
Discord, and (for cross-extension concerns) on [SEP-1913](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913).
