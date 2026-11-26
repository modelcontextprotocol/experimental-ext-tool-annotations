# Related work

External references and prior art relevant to the IG's trust / privacy
annotation work. Several were surfaced in IG meetings (notably 2026-05-28).

## SEPs

- [SEP-1913 — Trust and Sensitivity Annotations](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913) — the umbrella proposal these extensions derive from.
- [SEP-2061 — Action Security Metadata](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2061) — closed 2026-06-13; carried forward as `action-metadata`.
- [SEP-1862 — Tool Resolution / pre-flight checks](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1862) — core-protocol, composes with these extensions.
- [SEP-2133 — Extensions](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md) — the framework this repo incubates under.
- [SEP-2127 — Server Cards](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2893) — precedent for the Standards→Extensions Track refactor.
- [SEP-2787 — Tool Call Attestation](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2787) — candidate `evidenceRef` scheme.

## Research

- **FIDES** — *Information-flow control for LLM agents.* [arXiv:2505.23643](https://arxiv.org/abs/2505.23643). Basis for the `ifc.fides.v1` scheme in [`schemes/`](../schemes/).
- **Permissive Information-Flow Analysis for LLMs** — relaxes IFC join so a label propagates only when an input actually influences an output. [arXiv:2410.03055](https://arxiv.org/abs/2410.03055). Candidate `evidenceRef` scheme (per-result label), like FIDES.
- **AirGapAgent** — contextual-integrity minimisation: restrict per-task data to what the context warrants. [arXiv:2405.05175](https://arxiv.org/abs/2405.05175). Candidate scheme: emits a contextual-integrity classification per result.
- **Lineage-Aware Memory Governance** — derived items in agent memory carry their derivation lineage, and a read is re-checked against every ancestor's access policy, failing closed when lineage is missing. [doi:10.1109/ACCESS.2026.3730363](https://doi.org/10.1109/ACCESS.2026.3730363). Basis for the `lineage.derivation.v1` scheme in [`schemes/`](../schemes/).
- **CaMeL — Defeating Prompt Injections by Design** — capability-based control/data-flow extraction. [arXiv:2503.18813](https://arxiv.org/abs/2503.18813). A **host architecture**, not a data-label scheme (see note below); a capability token it issues could be referenced via `evidenceRef`, but the architecture itself is not a scheme.
- **Design Patterns for Securing LLM Agents** — IBM/Google/Microsoft. [arXiv:2506.08837](https://arxiv.org/abs/2506.08837). Plan-Then-Execute, Dual LLM, Map-Reduce, etc. Also **host architectures**, not schemes.
- **Trail of Bits** — prompt-injection via hidden content in GitHub issues. [blog](https://blog.trailofbits.com/2025/08/06/prompt-injection-engineering-for-attackers-exploiting-github-copilot/).
- **OpenAI Auto Review** — https://alignment.openai.com/auto-review/ (shared in IG chat).

### Schemes vs. host architectures

The `evidenceRef` slot carries **data labels** — a per-result record a server
can attach (FIDES, Permissive IFC, AirGapAgent, data-class, attestation
envelopes). It does **not** carry **host architectures** — control-flow designs
the *client/host* runs (CaMeL, the Design-Patterns catalogue, Dual-LLM). These
are complementary: an architecture decides what to do with a label, the label is
what a scheme produces. Only the former belong in [`schemes/`](../schemes/).

## Implementations & tooling

- [`kapil8811/mcp-trust-annotations`](https://github.com/kapil8811/mcp-trust-annotations) — reference Python SDK PoC for `trust-annotations`.
- [`github-mcp-server`](https://github.com/github/github-mcp-server) — public MCP server; emitter candidate for the `ifc-fides` scheme (knows repo visibility + collaborators).
- **Ethyca** data-labeling docs — https://www.ethyca.com/docs (shared in IG chat).
- **GitHub Next** agentic-workflows research on data labeling — to be documented as issues in this repo (IG action item, @gokhanarkan / @joannakl).

## Adjacent community proposals (from the SEP-1913 thread)

- **SINT Protocol** (capability-token constraint enforcement) — pshkv.
- **in-toto** attestations as a trust-annotation substrate.
- **OVERT 1.0** envelope shape for runtime evidence.
- Caller/tool **cosigning** model — viftode4.
- **Sequence-shape** policies — marras0914.

These are exactly the models that `evidenceRef`'s open `type` is designed to
accommodate as schemes — see [`schemes/`](../schemes/).
