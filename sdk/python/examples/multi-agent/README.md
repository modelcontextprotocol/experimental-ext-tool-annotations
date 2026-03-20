# UC-2: Multi-Agent Data Leak Prevention

Demonstrates how SEP-1913 annotations prevent PHI from leaking across agent boundaries.

## What it shows

Three agents cooperate on patient data:

```
Agent A (front-desk) → Agent B (analytics) → Agent C (external reporting)
```

- **Without annotations**: PHI flows freely A → B → C → leaked to public
- **With annotations**: Policy blocks B → C, redacts sensitive data in logs

## Usage

```bash
cd sdk/python
PYTHONPATH=src python examples/multi-agent/data_leak_prevention.py
```
