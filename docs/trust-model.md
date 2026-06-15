# Trust model

A single statement of the enforcement model shared across this repository's
extensions and data-labelling schemes, so individual specs don't re-litigate it.

## Annotations are claims, not guarantees

An annotation on a tool result or definition is a **claim** made by whoever
produced it. Nothing in these extensions assumes the producer is honest or
competent. The value of an annotation comes from two things:

1. **Verifiability.** Where a claim needs to be trusted, the `evidenceRef`
   pointer (see [`trust-annotations`](../specification/draft/trust-annotations.mdx))
   lets a consumer resolve and check the evidence behind it — re-hash the
   referenced record, verify a signature, check an inclusion proof — rather
   than taking the claim on faith.
2. **Accountability.** Enforcement lives with the parties that can impose
   consequences: **registries and marketplaces** that admit servers,
   **hosts/clients** that gate actions, and **operators** that set policy. The
   annotation gives those parties a machine-readable surface to act on.

This mirrors the framing repeated throughout the SEP-1913 discussion: trust
comes from the ecosystem verifying annotations, not from developer good faith.
A server that lies in its annotations is a server a registry can refuse to list
and a host can refuse to trust — the same accountability model as any other
declared capability.

## Defense in depth, not a single gate

As framed in the IG's inaugural meeting, these annotations are **defense in
depth**: they reduce the likelihood of unintended actions (unnecessary
destructive operations, data crossing a boundary it shouldn't), they don't
claim to be a complete security boundary. A host SHOULD combine them with its
own checks (its own injection detection, its own policy engine) rather than
treating any single annotation as authoritative.

## Human-in-the-loop on the risky edges

A recurring pattern from the IG research (Joanna's "phases" work, and the
SEP-1913 thread): rather than blanket-blocking flows a policy engine is unsure
about, **flag the specific call for user confirmation**. This preserves utility
while keeping a human on the genuinely risky edges, and is the recommended
default for `requiresReview` ([`action-metadata`](../specification/draft/action-metadata.mdx))
and for IFC policy violations (the [`ifc-fides`](../schemes/ifc-fides.md) scheme).

## Cross-domain is the hard case

Policy engines work well inside a single user/organization universe and
struggle across universes (cross-org, cross-domain flows). These extensions
provide the *signal* (where data came from, how sensitive it is, what a tool
does with it); they do not solve cross-domain enforcement on their own. That
remains an [open question](./open-questions.md) and a likely area for future
work (e.g. asymmetric crypto for domain integrity verification).
