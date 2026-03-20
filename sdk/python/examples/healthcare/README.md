# UC-1: Healthcare Data Protection

Demonstrates HIPAA-compliant data handling using SEP-1913 trust annotations.

## What it shows

- **Data classification**: Tools returning PHI are tagged `regulated(HIPAA)`, distinguishable from benign tools
- **Policy enforcement**: ALLOW / BLOCK / ESCALATE / REDACT decisions based on annotations
- **Destination constraints**: Patient data blocked from reaching external/public destinations

## Scripts

| Script | Description |
|--------|-------------|
| `mcp_client.py` | Connects to the server, calls all tools, applies policy enforcement |
| `host.py` | Policy-enforcing host with 8 scenarios (HIPAA forwarding, credential blocking, session escalation) |

## Usage

```bash
cd sdk/python
PYTHONPATH=src python examples/healthcare/mcp_client.py
PYTHONPATH=src python examples/healthcare/host.py
```
