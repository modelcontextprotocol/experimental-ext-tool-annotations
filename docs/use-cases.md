[Problem Statement](problem-statement.md) |
Use Cases |
[Approaches](approaches.md) |
[Open Questions](open-questions.md) |
[Experimental Findings](experimental-findings.md) |
[Related Work](related-work.md) |
[Contributing](../CONTRIBUTING.md)

# Use Cases

## UC-1: Healthcare Data Protection

A healthcare MCP server exposes tools for patient lookup, insurance processing, and staff directory queries. A host needs to enforce HIPAA-compliant data handling: patient data must not be forwarded to external services, and tools returning Protected Health Information (PHI) must be distinguishable from those returning non-sensitive data.

**Requires:** Data classification (`regulated(HIPAA)`), destination constraints, policy enforcement.

## UC-2: Multi-Agent Data Leak Prevention

In a multi-agent architecture, Agent A retrieves sensitive credentials from a vault tool and Agent B has access to an external email tool. Without sensitivity metadata and propagation tracking, there is no protocol-level mechanism to prevent Agent B from exfiltrating credential data it received from Agent A's context.

**Requires:** Sensitivity propagation across tool calls, session-level tracking, policy rules blocking credential egress.

## UC-3: Audit Logging for Compliance

An organization must maintain audit trails showing which tools accessed sensitive data, what classification the data had, and whether policy rules permitted or blocked the action. Current MCP provides no structured metadata to include in audit events.

**Requires:** Structured annotations on tool calls and results, policy decision logging.

## UC-4: User Consent for Sensitive Operations

A tool sends a notification to a patient via SMS. The host should be able to detect — from annotations, not just the tool description — that this tool has an external destination and involves PII, and therefore should prompt the user for confirmation before execution.

**Requires:** Destination metadata (`external`), sensitivity labels, client-side policy evaluation.

## UC-5: Progressive Adoption

Not all MCP server authors need full trust annotations. A simple internal tool may need no annotations at all, while a healthcare integration requires full classification, policy, and audit. The annotation system must support progressive adoption — from zero annotations to full enforcement — without requiring all-or-nothing commitment.

**Requires:** Optional annotations, graceful degradation, layered adoption levels.