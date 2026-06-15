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
- **Design Patterns for Securing LLM Agents** — IBM/Google/Microsoft. [arXiv:2506.08837](https://arxiv.org/abs/2506.08837). Plan-Then-Execute, Dual LLM, Map-Reduce, etc.
- **Trail of Bits** — prompt-injection via hidden content in GitHub issues. [blog](https://blog.trailofbits.com/2025/08/06/prompt-injection-engineering-for-attackers-exploiting-github-copilot/).
- **OpenAI Auto Review** — https://alignment.openai.com/auto-review/ (shared in IG chat).

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
