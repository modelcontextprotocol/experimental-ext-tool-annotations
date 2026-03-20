# Examples

Working demonstrations of SEP-1913 trust annotations, organized by use case.

```
_shared/        Shared Healthcare Clinic MCP server (used by all examples)
healthcare/     UC-1: Healthcare Data Protection — HIPAA policy enforcement
multi-agent/    UC-2: Multi-Agent Leak Prevention — cross-agent PHI containment
dashboard/      Interactive web UI for all scenarios
```

## Prerequisites

```bash
pip install mcp              # MCP Python SDK (stdio transport)
pip install starlette uvicorn  # only for dashboard
```

## Quick Start

```bash
cd sdk/python

# Run any example:
PYTHONPATH=src python examples/healthcare/mcp_client.py
PYTHONPATH=src python examples/healthcare/host.py
PYTHONPATH=src python examples/multi-agent/data_leak_prevention.py
PYTHONPATH=src python examples/dashboard/app.py
```

See each subfolder's README for details.
