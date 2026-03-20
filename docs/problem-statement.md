Problem Statement |
[Use Cases](use-cases.md) |
[Approaches](approaches.md) |
[Open Questions](open-questions.md) |
[Experimental Findings](experimental-findings.md) |
[Related Work](related-work.md) |
[Contributing](../CONTRIBUTING.md)

# Problem Statement

MCP tools today are semantically opaque when it comes to data sensitivity. A tool's definition includes its name, description, and input schema — but nothing about the nature of the data it returns or processes. Consider these two tools:

```jsonc
// Tool 1: System health check
{
  "name": "health_check",
  "description": "Check if the system is running",
  "inputSchema": {}
}

// Tool 2: Patient record lookup
{
  "name": "patient_lookup",
  "description": "Look up a patient record from the EHR",
  "inputSchema": {
    "type": "object",
    "properties": { "patient_id": { "type": "string" } }
  }
}
```

At the protocol level, these tools are indistinguishable in terms of data sensitivity. Both are just callable functions. Yet one returns benign system status, while the other returns Protected Health Information (PHI) regulated under HIPAA law. There is no machine-readable signal that allows a host to differentiate between them.

## Key Gaps

### No Sensitivity Metadata

Tools carry no data classification labels. A host cannot distinguish a tool returning public system metrics from one returning PII, financial records, or credentials. Without classification, all tool outputs are treated equally — which means sensitive data receives no additional protection.

### No Destination Awareness

The protocol does not express where tool outputs may flow. A tool that sends an email to an external address, writes to a third-party API, or stores data in a public bucket looks identical to one that only returns data to the user. Hosts have no structured way to assess data egress risk.

### No Policy Enforcement Surface

Without structured annotations, security policies cannot be evaluated at the protocol level. Organizations cannot express rules like "never send credentials to external destinations" or "require user confirmation before forwarding PII" — because the primitives to describe sensitivity and destination don't exist.

### LLM-Dependent Safety

Data flow decisions currently rely entirely on the LLM's interpretation of tool descriptions. This can be bypassed by:

- **Prompt injection** — Malicious content in tool outputs can instruct the model to misroute data
- **Hallucination** — The model may fabricate a safe interpretation of an ambiguous description
- **Inadequate descriptions** — Tool authors may not describe sensitivity in human-readable text

⚠️ The common thread: the host has no structured metadata to make informed decisions about data flow.