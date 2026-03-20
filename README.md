# experimental-ext-tool-annotations

> ⚠️ **Experimental** — This repository is an incubation space for the Tool Annotations Interest Group. Contents are exploratory and do not represent official MCP specifications or recommendations.

## Mission

This Interest Group explores how MCP tool annotations can be enhanced to support data classification, sensitivity labeling, and provenance tracking — enabling hosts and clients to make informed, policy-driven decisions about data flow across tool boundaries.

As a starting point, we are contributing a reference SDK implementation based on [SEP-1913](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913) (Trust & Sensitivity Annotations).

## Scope

### In Scope

- **Requirements gathering:** Documenting use cases and constraints for tool-level data sensitivity metadata
- **Pattern exploration:** Testing and evaluating annotation schemas, policy enforcement models, and sensitivity propagation strategies
- **Proof of concepts:** Maintaining a shared repo of reference implementations and experimental findings (starting with the SEP-1913 Python SDK)

### Out of Scope

- **Approving spec changes:** This IG does not have authority to approve protocol changes; recommendations flow through the SEP process
- **Implementation mandates:** We can document patterns but not require specific client or server behavior

## Problem Statement

MCP tools today are semantically opaque when it comes to data sensitivity. A tool's definition includes its name, description, and input schema — but nothing about the nature of the data it returns or processes. There is no machine-readable signal that allows a host to differentiate a benign health check from a HIPAA-regulated patient record lookup.

- **No sensitivity metadata** — Tools carry no data classification labels; hosts cannot distinguish PII from public data
- **No destination awareness** — The protocol does not express where tool outputs may flow (storage, third-party APIs, user display)
- **No policy enforcement surface** — Without structured annotations, security policies cannot be evaluated at the protocol level
- **LLM-dependent safety** — Data flow decisions rely entirely on the LLM's interpretation of tool descriptions, which can be bypassed by prompt injection, hallucination, or inadequate descriptions

See the [Problem Statement](docs/problem-statement.md) for full details.

## Repository Contents

| Document | Description |
| :--- | :--- |
| [Problem Statement](docs/problem-statement.md) | Current limitations and gaps |
| [Use Cases](docs/use-cases.md) | Key use cases driving this work |
| [Approaches](docs/approaches.md) | Approaches being explored (not mutually exclusive) |
| [Open Questions](docs/open-questions.md) | Unresolved questions with community input |
| [Experimental Findings](docs/experimental-findings.md) | Results from implementations and testing |
| [Related Work](docs/related-work.md) | SEPs, implementations, and external resources |
| [Contributing](CONTRIBUTING.md) | How to participate |
| [Python SDK](sdk/python/) | Reference implementation (SEP-1913, 138 tests) |

## Facilitators

| Role | Name | Organization | GitHub |
| :--- | :--- | :--- | :--- |
| TO BE ADDED | TO BE ADDED | TO BE ADDED| TO BE ADDED |

## Lifecycle

**Current Status: Active Exploration**

### Graduation Criteria (IG → WG)

This IG may propose becoming a Working Group if:

- Clear consensus emerges on an annotation schema requiring sustained spec work
- Cross-cutting coordination requires formal authority delegation
- At least two Core Maintainers sponsor WG formation

### Retirement Criteria

- Problem space resolved (conventions established, absorbed into other WGs)
- Insufficient participation to maintain momentum
- Community consensus that tool annotations don't belong in MCP protocol scope

## Work Tracking

| Item | Status | Champion | Notes |
| :--- | :--- | :--- | :--- |
| Repository scaffolding | Done | All facilitators | Align structure with other experimental-ext repos |
| Problem statement & use cases | Done | All facilitators | Document motivating scenarios and constraints |
| SEP-1913 reference SDK | Done | TBD | Python SDK implementing trust & sensitivity annotations (138 tests passing) |
| Experimental findings | Proposed | TBD | Usability study results and implementation learnings |

## Success Criteria

- **Short-term:** Documented consensus on requirements and evaluation of existing annotation approaches
- **Medium-term:** Clear recommendation (annotation schema convention vs. protocol extension vs. both)
- **Long-term:** Interoperable tool annotation convention across MCP servers and clients

