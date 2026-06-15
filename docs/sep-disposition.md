# SEP disposition: what happens to the existing proposals

This document explains how the existing trust/privacy/annotation SEPs map onto
the experimental extensions incubated in this repository, and what is proposed
to happen to each SEP. It exists so that anyone arriving from one of those PRs
can understand the plan without reading the whole thread.

> **Status:** proposal / options. Nothing here is decided until reflected in the
> relevant SEP PRs. The migration follows the precedent set by
> [SEP-2127 → Extensions Track (#2893)](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2893).

## Why anything changes

When [SEP-1913](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913)
was first framed, the **Extensions Track** ([SEP-2133](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md))
and the `experimental-ext-*` incubation process did not exist in their current
form. Two inputs since then point at a different shape:

1. **Sponsor steer.** [@localden](https://github.com/localden) asked for a
   *narrower first cut* — a single broad taxonomy with array-or-scalar enum
   polymorphism is hard to remove or change once shipped.
2. **IG decision.** The Tool Annotations IG
   [aligned on 2026-05-28](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2820)
   to pursue this work as an **experimental extension first**, build an
   adoption/evidence base, and only then ask core maintainers to absorb
   anything into the protocol.

The result: split the schema-bearing parts into small, independent extensions,
each able to graduate on its own clock.

## The precedent: SEP-2127 (Server Cards)

[#2893](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2893)
refactored SEP-2127 from **Standards Track** to **Extensions Track**:

- Frontmatter `Type: Standards Track` → `Type: Extensions Track`, plus an
  `Extension Identifier` and "on behalf of the WG" attribution.
- A top-of-file `<Note>` pointing at the experimental repo as the spec home.
- The SEP body **slimmed to a charter** — Abstract, Motivation, Rationale, a
  high-level Specification *pointer*, security posture *summary* — with the
  detailed normative wire format delegated to the extension repo.
- The SEP body kept **non-temporal**: a published SEP is frozen, so in-flight
  "open items" live in the PR description and extension-repo issues, not in the
  SEP text.

We apply the same playbook below.

## Per-SEP disposition

### SEP-1913 — Trust and Sensitivity Annotations

**Proposed:** becomes the **umbrella / problem-framing** thread. The schema-
bearing content moves into the extensions below. Options, in order of
preference:

- **(A, preferred)** Keep the PR open as the framing umbrella; add an intent
  comment (see [below](#intent-comment)); later, either refactor it to an
  Extensions Track *charter* that points here (SEP-2127 shape) **or** close it
  in favor of per-extension Extensions Track SEPs once those are ready.
- **(B)** Refactor 1913 itself into the `trust-annotations` Extensions Track
  SEP and spin the others off as siblings.
- **(C)** Close 1913 outright and open three fresh Extensions Track SEPs. Loses
  the discussion history's continuity; not preferred.

**Moved into extensions:** `trust-annotations`, `action-metadata`.
**Moved into `schemes/`:** the IFC/FIDES work, as one data-labelling **scheme**
(`ifc.fides.v1`) that fills the `trust-annotations` `evidenceRef` slot — not an
extension and not a sibling of the two above.
**Parked on the umbrella:** `maliciousActivityHint`,
session-level propagation rules. See [open-questions.md](./open-questions.md).

### SEP-2061 — Action Security Metadata

**Disposition:** **closed 2026-06-13** in favour of the
[`action-metadata`](../specification/draft/action-metadata.mdx) extension.
SEP-2061 is by [@rreichel3](https://github.com/rreichel3), who is also an IG
co-facilitator and SEP-1913 co-author, so this was a fold-in, not a collision.
[@localden](https://github.com/localden) closed the PR (no active sponsor) after
agreeing the extension is the right home; the extension now carries the field
semantics forward, with SEP-2061 preserved as the origin and credit.

### SEP-1862 — Tool Resolution (pre-flight checks)

**Proposed:** **stays Standards Track / core.** The 2026-05-28 IG meeting
concluded pre-flight checks are inherently a protocol-level change, not an
extension. These extensions are deliberately **response-level** (`_meta` on
results, static `ToolAnnotations`) and do **not** depend on 1862. They compose
with it if it lands, but do not block on it.

### Other related SEPs (not owned here)

- **SEP-1984 (Comprehensive Tool Annotations)**, **SEP-2417 (Model Preferences
  for Tools)** — tracked by the IG as discussion items; not part of these
  extensions. Cross-link only.
- **SEP-2787 (Tool Call Attestation)** and the various attestation/evidence
  threads — these are natural `evidenceRef` **scheme** candidates rather than
  competitors. Coordinate so the `evidenceRef.type` registry can list them.

## Mapping table

| SEP | Title | Proposed disposition | Extension home |
| :-- | :-- | :-- | :-- |
| 1913 | Trust & Sensitivity Annotations | Umbrella thread; schema moves to extensions | `trust-annotations` (+ `schemes/ifc-fides`) |
| 2061 | Action Security Metadata | **Closed 2026-06-13**; lives as extension | `action-metadata` |
| 1862 | Tool Resolution (pre-flight) | Stays core / Standards Track | — (composes, no dependency) |
| 1984 | Comprehensive Tool Annotations | IG discussion item | — |
| 2417 | Model Preferences for Tools | IG discussion item | — |
| 2787 | Tool Call Attestation | Candidate `evidenceRef` profile | (future) |

## Intent comment

The text we plan to post on SEP-1913 (and, abbreviated, on SEP-2061) lives in
[intent-comment.md](./intent-comment.md) so it can be reviewed before posting
and kept in sync with this document.
