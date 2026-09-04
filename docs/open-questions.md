# Open questions

Tracked here rather than in the spec drafts, so the drafts stay non-temporal.

## Cross-cutting

- **Where does the policy-enforcement engine live** across different user
  universes (cross-org, cross-domain)? Engines work well within one universe;
  cross-domain is the hard case. (IG 2026-05-28.)
- **Cross-domain integrity verification** — is asymmetric crypto for domain
  identity in scope for a future extension, or out of scope entirely? CLI tools
  remain a persistent gap for enforcing these constraints.
- **`evidenceRef.type` registry** — who curates the list of well-known scheme
  types, and how do we coordinate with attestation SEPs (e.g. SEP-2787) so
  values don't collide?

## trust-annotations

- **Sensitivity beyond the floor.** The `sensitive` boolean is settled as the
  **lowest-common-denominator floor** — a basic, general signal every client can
  act on, "better than nothing," with servers encouraged to *also* emit a richer
  scheme (see the [decision log](./decisions.md) and the "emit both" guidance in
  the spec). The residual open question is narrower: is "coarse boolean + richer
  `evidenceRef` scheme" sufficient for regulated flows, or do some hosts need the
  classification expressible *on the wire* without a scheme? Current lean: **no
  wire escape hatch** — keep the wire floor un-rottable and push the taxonomy
  into [`data-class.v1`](../schemes/data-class.md). Background on why a single
  scalar/enum was rejected: sensitivity is set-theoretic not linear
  ([@JustinCappos](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2967516811)),
  reviewers wanted org-defined vocabularies
  ([@olaservo](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2968743154),
  [@Mossaka](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2971788308))
  and a class+regulatory pairing
  ([@krubenok](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#discussion_r3103485194)),
  and a baked-in taxonomy is hard to remove
  ([@localden](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#issuecomment-4037623595)).
- **Enforcement vs. advisory.** A self-declared `sensitive: true` from a
  poorly-configured or malicious server could create a false sense of security
  ([@localden](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#issuecomment-4037623595)).
  [docs/trust-model.md](./trust-model.md) puts verification in registries; is
  that enough without a normative client-side check path?
- Content-block-level vs. result-level attachment — does the draft need a
  worked multi-result example before it's implementable? Per-block annotation
  with **byte/codepoint ranges** was requested so clients can highlight the
  flagged span, not just the whole result
  ([@connor4312](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#issuecomment-3849207989)).
- `list_changed`: confirmed response-level annotations don't participate; revisit
  only if trust vocabulary ever attaches to tool definitions.

## Naming (under review)

These are explicitly unsettled and are being reviewed against the SEP-1913
record before any rename lands:

- **Umbrella name.** The original SEP was "Trust *& Sensitivity* Annotations" —
  two axes (integrity *and* confidentiality). `trust-annotations` reads as the
  integrity half; does the name hide the `sensitive` (confidentiality) half?
- **`untrusted` vs `openWorldHint`.** Same concept, different layer (result vs.
  tool definition). Share a name/vocabulary, or keep them deliberately distinct?
- **`evidenceRef.type` vs `evidenceRef.scheme`.** The repo calls these values
  "schemes" (`schemes/`); the selector field is `type`. Align the field name?
- **`evidenceRef` itself.** Its ancestor is [@pshkv](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#issuecomment-4196867926)'s
  `decision_ref` / `attestation_ref` / `policy_profile`. Is `evidenceRef` the
  clearest umbrella, or should the pointer name the kind of thing it references?

## action-metadata

- Coexistence vs. replacement of legacy `destructiveHint` / `readOnlyHint` /
  `idempotentHint` / `openWorldHint`.
- Open strings vs. closed enums for `destination` / `source` / `sensitivity`.
- Does `requiresReview` need a machine-readable *reason* for good client UX?

## display-templates

- **Branch-key spelling.** Should the branch-scoped key inside `oneOf`/`anyOf`
  subschemas be spelled `x-mcp-display-template`, following the
  [SEP-2356](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2356)
  precedent for schema-embedded extension keywords, rather than the reverse-DNS
  spelling in the draft?
- **Result-side attachment point.** Per-content-block only, or also permitted at
  the `CallToolResult` level (one string per result) for servers whose results
  are multi-block but whose human summary is singular?
- **Inner key naming.** `template` / `text` versus more explicit spellings
  (`callTemplate` / `displayText`).
- **One string or two?** gemini-cli found it needed both a description of the
  call (`getDescription()`) and a shorter title for the UI
  (`getDisplayTitle()`), and Codex caps its Node REPL title at 80 graphemes.
  This extension defines a single `template`. Is one string enough, or do
  constrained surfaces (status lines, one-line logs, notification text) need a
  short form alongside the fuller preview? Raised by the 2026-09-04 client
  survey rather than by review.

## ifc-fides (scheme)

- Inline `_meta.ifc` for low-friction adoption vs. always behind `evidenceRef`.
- GitHub Enterprise `internal` repo visibility → `public`/`private` mapping
  (audience is the whole org, broader than collaborators; resolved host-side).
- Reader-set resolution is host-side by design — confidentiality join across two
  `private` sources needs the intersection, which the opaque wire marker can't
  express. Is the 3-step host resolution enough, or do some hosts need a
  standard `evidenceRef.ref` shape to locate the originating system?

## Parked (SEP-1913 umbrella)

- **`maliciousActivityHint`** — killed in review on three grounds
  ([@connor4312](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913#issuecomment-3849207989)):
  it can't be resolved before execution for dynamic tools; a boolean gives no
  UX or ranges; and clients won't trust a server's self-report of its own
  maliciousness. If it returns, it is per-`ContentBlock` with spans, driven by
  the **host's** own detection, not a server-attested boolean.
- **Taint persistence across the store boundary** — a label must survive
  round-tripping through storage: write a card number to a file, read it back,
  and the sensitivity label must not silently disappear
  ([@JustinCappos](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/711#issuecomment-2967516811)).
  This is a propagation property no single response annotation can guarantee on
  its own; it needs the taxonomy and `evidenceRef` stable first.
- **Session-level propagation rules** — escalation semantics and the
  **sequence-shape** gap: "this was call N in a flagged sequence" has no response
  annotation surface today ([marras0914](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913)).
  A candidate `evidenceRef` scheme could carry a sequence assertion; tracked in
  [`schemes/README.md`](../schemes/README.md).
