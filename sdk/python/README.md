# mcp-trust-annotations

> SEP-1913 Trust & Sensitivity Annotations SDK for the Model Context Protocol

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

The first implementation of [SEP-1913: Trust and Sensitivity Annotations](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913) for Python. Annotate your MCP tools with data classification metadata, track sensitivity propagation across agent sessions, and enforce security policies — all with zero external dependencies.

---

## Why This Exists

MCP tools can read patient records, send emails, deploy services, and process payments — but there's no standard way to tell a client **what kind of data a tool handles**. SEP-1913 proposes adding trust and sensitivity annotations to the MCP spec. This SDK implements those types so you can start using them today.

**Without annotations:**
```
Agent reads patient record → Agent sends email with patient data → 💥 HIPAA violation
```

**With annotations + policy enforcement:**
```
Agent reads patient record → Session marked as HIPAA-regulated →
Agent tries to send email to public → ❌ BLOCKED by policy engine
```

---

## Installation

```bash
cd sdk/python
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+. No external dependencies.

---

## Quick Start

### 1. Annotate a Tool

```python
from annotate import trust_annotated
from trust_types import ReturnMetadata, Source, Regulated

@trust_annotated(
    return_metadata=ReturnMetadata(
        source=Source.INTERNAL,
        sensitivity=Regulated.of("HIPAA"),
    ),
    attribution=("Epic-EHR",),
)
async def patient_lookup(patient_id: str) -> dict:
    """Look up a patient record from the EHR system."""
    return await ehr.get_patient(patient_id)
```

### 2. Serialize to MCP Wire Format

```python
from annotate import get_trust_annotations, to_wire

ann = get_trust_annotations(patient_lookup)
wire = to_wire(ann)

# Use in your MCP tools/list response:
tool_def = {
    "name": "patient_lookup",
    "description": "Look up a patient record",
    "inputSchema": { ... },
    "annotations": {
        "readOnlyHint": True,
        **wire,   # ← SEP-1913 fields injected here
    },
}
```

### 3. Track Session Propagation

```python
from propagate import SessionTracker
from trust_types import ResultAnnotations, SimpleDataClass, Regulated

tracker = SessionTracker(session_id="session-001")

# After calling health_check (no sensitive data)
tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE), "health_check")

# After calling patient_lookup (HIPAA-regulated)
tracker.merge(
    ResultAnnotations(sensitivity=Regulated.of("HIPAA"), attribution=("Epic-EHR",)),
    "patient_lookup",
)
print(tracker.session.max_sensitivity)  # → Regulated(HIPAA)

# Sensitivity never de-escalates
tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE), "health_check")
print(tracker.session.max_sensitivity)  # → still Regulated(HIPAA)
```

### 4. Enforce Policies

```python
from policy import PolicyEngine

engine = PolicyEngine(mode="enforce")  # "audit" | "warn" | "enforce"
engine.register_tool("patient_lookup", wire)

decision = engine.evaluate(
    "patient_lookup",
    action="call",
    target_destination="public",
)
print(decision.allowed)   # → False
print(decision.reason)    # → "Regulated data (HIPAA) cannot leave organization"
```

### 5. Enable Audit Logging

```python
from emit import enable_logging

enable_logging(agent_id="urn:agent:my-app")
```

---

## Running Tests

```bash
cd sdk/python
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Architecture

```
src/
├── trust_types.py  # SEP-1913 type definitions (enums, dataclasses)
├── annotate.py     # @trust_annotated decorator, to_wire/from_wire
├── propagate.py    # SessionTracker: sensitivity escalation
├── policy.py       # PolicyEngine: audit/warn/enforce modes
└── emit.py         # Structured JSON audit logging
```

**Dependency rule:** Modules only import downward. `emit.py` ↔ `annotate.py` circular dependency is resolved via lazy imports inside function bodies.

---

## Examples

The `examples/` directory contains working demonstrations of SEP-1913 annotations, organized by use case:

```
examples/
  _shared/              # Shared MCP server used by all examples
  healthcare/           # UC-1: HIPAA policy enforcement
  multi-agent/          # UC-2: Cross-agent PHI leak prevention
  dashboard/            # Interactive web UI for all scenarios
```

**Prerequisites:** `pip install mcp` (the official MCP Python SDK, for stdio transport)

### Shared Server

The Healthcare Clinic MCP server in `examples/_shared/` is used by all examples. It exposes 8 annotated tools (health check, patient lookup, staff directory, insurance claims, API key rotation, notifications) with varying sensitivity levels, destinations, and outcomes.

```bash
cd sdk/python
PYTHONPATH=src python examples/_shared/mcp_server.py
```

### UC-1: Healthcare Data Protection

Demonstrates HIPAA-compliant data handling — patient data must not be forwarded to external services, and tools returning PHI must be distinguishable from non-sensitive tools.

```bash
cd sdk/python

# Client: connects via stdio, calls tools, shows policy enforcement
PYTHONPATH=src python examples/healthcare/mcp_client.py

# Host: builds a PolicyEngine from annotations, demonstrates ALLOW / BLOCK / ESCALATE / REDACT
PYTHONPATH=src python examples/healthcare/host.py
```

### UC-2: Multi-Agent Data Leak Prevention

Three agents (front-desk → analytics → external reporting) handling HIPAA patient data. Shows how PHI leaks freely without annotations vs. how SEP-1913 policy enforcement blocks the leak deterministically.

```bash
cd sdk/python
PYTHONPATH=src python examples/multi-agent/data_leak_prevention.py
```

### Web Dashboard

```bash
cd sdk/python
pip install starlette uvicorn
PYTHONPATH=src python examples/dashboard/app.py
```

Opens at http://localhost:8913. Interactive web UI for:
- Viewing all server tools and their SEP-1913 annotations
- Calling tools interactively
- Running UC-1, UC-2, and host scenarios
- Executing usability tests
- Building custom policy enforcement tests

**Note**: Start mcp server and dashboard using script:

On Linux/macOS:
```bash
cd sdk/python/examples/dashboard
chmod +x start_dashboard.sh
./start_dashboard.sh
```

On Windows (PowerShell):
```powershell
cd sdk\python\examples\dashboard
.\start_dashboard.ps1
```
