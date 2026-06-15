# Open questions

Tracked here rather than in the spec drafts, so the drafts stay non-temporal.

## Cross-cutting

- **Where does the policy-enforcement engine live** across different user
  universes (cross-org, cross-domain)? Engines work well within one universe;
  cross-domain is the hard case. (IG 2026-05-28.)
- **Cross-domain integrity verification** — is asymmetric crypto for domain
  identity in scope for a future extension, or out of scope entirely? CLI tools
  remain a persistent gap for enforcing these constraints.
- **`evidenceRef.type` registry** — who curates the list of well-known profile
  types, and how do we coordinate with attestation SEPs (e.g. SEP-2787) so
  values don't collide?

## trust-annotations

- Is `sensitive` the right single coarse signal, or do we need the
  `data-class.v1` profile from day one?
- Content-block-level vs. result-level attachment — does the draft need a
  worked multi-result example before it's implementable?
- `list_changed`: confirmed response-level annotations don't participate; revisit
  only if trust vocabulary ever attaches to tool definitions.

## action-metadata

- Coexistence vs. replacement of legacy `destructiveHint` / `readOnlyHint` /
  `idempotentHint` / `openWorldHint`.
- Open strings vs. closed enums for `destination` / `source` / `sensitivity`.
- Does `requiresReview` need a machine-readable *reason* for good client UX?

## ifc-fides (scheme)

- Inline `_meta.ifc` for low-friction adoption vs. always behind `evidenceRef`.
- GitHub Enterprise `internal` repo visibility → `public`/`private` mapping
  (audience is the whole org, broader than collaborators; resolved host-side).
- Reader-set resolution is host-side by design — confidentiality join across two
  `private` sources needs the intersection, which the opaque wire marker can't
  express. Is the 3-step host resolution enough, or do some hosts need a
  standard `evidenceRef.ref` shape to locate the originating system?

## Parked (SEP-1913 umbrella)

- **`maliciousActivityHint`** — if it returns, it is per-`ContentBlock` with
  spans, driven by the host's own detection, not a server-attested boolean.
- **Session-level propagation rules** — escalation semantics and the
  sequence-shape gap ("this was call N in a flagged sequence" has no response
  annotation surface today).
