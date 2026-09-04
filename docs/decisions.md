# Decision log

Append-only record of design decisions for the Tool Annotations IG's trust /
privacy extension work. Newest at the bottom.

## 2026-06-10 — Split SEP-1913 into independent extensions

**Decision.** Split the schema-bearing parts of SEP-1913 into separate
experimental extensions, each with its own `io.modelcontextprotocol/…`
identifier and reference implementation, rather than pursuing one broad
Standards Track SEP.

**Rationale.** @localden's review asked for a *narrower first cut*; the IG
[aligned 2026-05-28](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2820)
on an extension-first strategy. Independent extensions can graduate on their own
clock and avoid hard-to-remove schema.

## 2026-06-10 — Three initial extensions

**Decision.** `trust-annotations` (primary), `action-metadata`, `ifc-fides`.

**Rationale.** These are the three pieces with either a reference implementation
or an existing SEP behind them: Kapil's SDK, SEP-2061 (Reichel), and the FIDES
model respectively.

## 2026-06-10 — FIDES is a profile, not a top-level extension

**Decision.** Information-flow control is `type: "ifc.fides.v1"`, a profile of
the `trust-annotations` `evidenceRef` slot — not a top-level `io.modelcontextprotocol/ifc`
extension.

**Rationale.** IFC is one enforcement model among several raised in review
(capability tokens — pshkv; cosigning — viftode4; sequence shape — marras0914).
A top-level `ifc/` root would foreclose those. Reviewer endorsement was for IFC
"if you use annotations" — i.e. as a profile.

## 2026-06-10 — `evidenceRef.type` is an open string

**Decision.** `type` MUST remain an open string with a non-binding registry of
well-known values; never a closed enum. Required fields are `digest` and
`canonicalization`; `schema` recommended; `ref` optional.

**Rationale.** Adapted from the vaaraio / Rul1an convergence in the SEP-1913
thread. An open `type` is what lets IFC, data-class, sequence-shape, and
attestation profiles share one slot.

## 2026-06-10 — `requiresReview` moves to `action-metadata`

**Decision.** `requiresReview` is an `action-metadata` field, not a
`trust-annotations` field.

**Rationale.** It is a workflow/consent signal, not a data-classification
property. Keeping it out of the trust taxonomy avoids reproducing SEP-1913's
"several concerns in one schema" problem at smaller scale.

## 2026-06-10 — DataClass demoted to a profile

**Decision.** The wire taxonomy keeps only the coarse `sensitive` boolean.
The four-level classification + regulatory scope becomes an `evidenceRef`
profile `type: "data-class.v1"`.

**Rationale.** Coarse binary is universally client-actionable and cheap on the
wire; the richer taxonomy can evolve behind a profile without a breaking schema
change.

## 2026-06-10 — Parked: maliciousActivityHint, propagation rules

**Decision.** Neither becomes an extension now; both stay on the SEP-1913
umbrella.

**Rationale.** `maliciousActivityHint` has unresolved structural objections
(fires pre-execution at `tools/resolve`; boolean granularity wrong for UX;
clients won't trust server self-attestation). Propagation/sequence-shape needs
the taxonomy and `evidenceRef` stable first.

## 2026-06-10 — Citations: public sources only

**Decision.** Reference implementations and motivating examples cite **public**
artifacts — [`github-mcp-server`](https://github.com/github/github-mcp-server),
[`kapil8811/mcp-trust-annotations`](https://github.com/kapil8811/mcp-trust-annotations),
[arXiv:2505.23643](https://arxiv.org/abs/2505.23643) — and index on the public
SEP-1913 review record (esp. @localden). Private/internal implementations are
not named or linked.

## 2026-06-10 — Pre-flight (SEP-1862) stays core

**Decision.** These extensions are response-level and do not depend on Tool
Resolution. SEP-1862 remains a core/Standards-Track protocol change.

**Rationale.** The 2026-05-28 IG meeting concluded pre-flight is inherently a
protocol-level change, not an extension.

## 2026-06-16 — FIDES is a scheme, not a sibling extension

**Decision.** Refines the 2026-06-10 "FIDES is a profile" decision. The IFC/FIDES
work moves out of `specification/draft/` (where it sat next to the two
extensions) into a `schemes/` folder. There are **two** extensions
(`trust-annotations`, `action-metadata`); FIDES is **one data-labelling scheme**
(`ifc.fides.v1`) that fills the `trust-annotations` `evidenceRef` slot.

**Rationale.** FIDES is one model the extension *could* use, not a peer of the
extensions, and must not be presented as a sibling. The original SEP cites it
alongside ShardGuard and "Design Patterns for Securing LLM Agents," and the
SEP-1913 thread adds capability tokens, cosigning, sequence-shape, and
attestation models — so `schemes/` is a folder for interchangeable approaches,
with FIDES as the first worked one. This shows the range the open `evidenceRef`
slot is meant to carry rather than implying IFC is the privileged model.

## 2026-06-16 — Three pull requests, stacked

**Decision.** The work ships as three PRs: `trust-annotations` (the base,
carrying shared repo scaffolding), `action-metadata` (stacked on the base), and
the FIDES scheme in `schemes/` (stacked on the base). The two extensions are
independent; the FIDES scheme depends on `trust-annotations` because it fills
that extension's `evidenceRef` slot.

**Rationale.** Separate PRs let each piece be reviewed and graduate on its own
clock. FIDES stacks on `trust-annotations` because a scheme has no meaning
without the slot it fills.

## 2026-06-16 — Schemes carry data labels; host architectures do not

**Decision.** `schemes/` holds **data-labelling** approaches a server attaches to
a result (FIDES, Permissive IFC, AirGapAgent, `data-class`, attestation
envelopes). **Host architectures** — control-flow designs the client/host runs
(CaMeL, the "Design Patterns for Securing LLM Agents" catalogue, Dual-LLM) — are
prior art in [`related-work.md`](./related-work.md), not candidate schemes.

**Rationale.** A scheme produces a label; an architecture decides what to do with
one. Conflating them would invite a `schemes/camel.md` that has no per-result
payload to define. A capability token such an architecture issues can still be
*referenced* through `evidenceRef`, but the architecture itself is not a scheme.

## 2026-06-16 — Early SEP-1913 feedback recorded as cited open questions

**Decision.** The substantive concerns from the original issue (#711) and SEP
(#1913) review — the set-theoretic critique of linear sensitivity, org-defined
vocabularies, the class+regulatory pairing, taint persistence across storage,
per-block byte ranges, sequence-shape, and the false-security risk — are
captured with reviewer attributions in [`open-questions.md`](./open-questions.md)
rather than silently dropped by the narrower cut.

**Rationale.** The narrow first cut (`sensitive: boolean`) deliberately omits a
lot of debated design. Recording *why*, with links to the people who raised each
point, keeps the history visible and gives each parked item a home to graduate
from (a scheme, an `action-metadata` field, or a future extension) instead of
being re-litigated from scratch.

## 2026-06-16 — `sensitive` is a lowest-common-denominator floor; emit both

**Decision.** The coarse `sensitive` boolean is intentionally a
lowest-common-denominator signal — a universal, always-actionable floor that
supports a basic "better than nothing" egress/consent policy even against a
barely-known server. It is the basic, general scheme every participant
understands, **not** a competitor to richer schemes. Servers SHOULD emit **both**
the boolean and a richer `evidenceRef` scheme (e.g. `data-class.v1`,
`ifc.fides.v1`) where they can; `sensitive` MUST NOT be dropped merely because a
scheme is present.

**Rationale.** Clarifies the original purpose of the boolean (raised by Sam): the
point of keeping it on the wire was never to *replace* richer classification but
to guarantee a floor any client can act on. Richer schemes are strictly more
capable but are not universally implemented, so they cannot be the floor —
layering the two gives universal actionability without capping what advanced
hosts can do. This also answers the "boolean vs. richer taxonomy" tension from
SEP-1913 review: it is not either/or, it is both, at different layers.

- 2026-08-04 — display-templates: wire carrier is the extension-namespaced
  `_meta` key (`io.modelcontextprotocol/display-templates`), not new
  `ToolAnnotations`/`Annotations` fields: matches the trust-annotations
  precedent in this repo, follows SEP-2133's independent-graduation path,
  and is the only carrier that survives the Python SDK 2.x strict models,
  which strip unknown annotation keys at both serialization ends.

- 2026-09-04 — display-templates: the motivation rests on observed client
  behaviour rather than on argument alone. Six agentic CLIs were surveyed by
  reading their rendering code: goose, gemini-cli, Codex, opencode, cline and
  (from observed output, since it is closed source) Claude Code. All six render
  tool calls to a human, all six special-case some tools by name, and in all six
  that path is reachable only by first-party tools; anything discovered over MCP
  has its arguments dumped. Two have already built partial, non-interoperable
  versions of this mechanism: Codex reads a `title` argument for Node REPL
  servers, and opencode prefers a `state.title` over its JSON fallback.

  **Rationale.** This changes what the proposal is arguing. Not that clients
  ought to start rendering tool calls legibly, which invites a debate about
  whether it is worth doing, but that they already do it, privately and
  incompatibly, and that MCP servers are the only participants excluded. It also
  answers the field-descriptions objection empirically: none of these renderers
  consults a model, so a static description in the schema cannot reach them.
