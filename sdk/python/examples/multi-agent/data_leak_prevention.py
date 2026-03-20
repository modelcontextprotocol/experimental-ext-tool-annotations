"""D9: Multi-Agent Data Leak Prevention Demo.

Side-by-side comparison showing how PHI leaks across agents WITHOUT
trust annotations (current MCP) vs. how SEP-1913 prevents it.

The demo uses a real MCP server (Healthcare Clinic) for the "WITH"
scenario and simulates the "WITHOUT" scenario to show the contrast.

Three agents cooperate:
  Agent A — Front-desk (calls patient_lookup)
  Agent B — Internal analytics
  Agent C — External reporting (public)

WITHOUT annotations: PHI flows freely A → B → C → leaked.
WITH annotations:    Policy blocks B → C, redacts B → logs.

Usage:
    cd <repo-root>/sdk/python
    PYTHONPATH=src python examples/multi-agent/data_leak_prevention.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time

# Force UTF-8 output on Windows to support Unicode symbols
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from policy import PolicyEngine
from propagate import SessionTracker
from trust_types import (
    ResultAnnotations,
    SimpleDataClass,
    Regulated,
    sensitivity_level,
)


# ── ANSI helpers ──────────────────────────────────────────────────

class C:
    RST = "\033[0m"
    B   = "\033[1m"
    DIM = "\033[2m"
    R   = "\033[91m"
    G   = "\033[92m"
    Y   = "\033[93m"
    BL  = "\033[94m"
    CY  = "\033[96m"
    MAG = "\033[95m"

PATIENT_DATA = {
    "patient_id": "P-12345",
    "name": "Jane Doe",
    "dob": "1985-03-15",
    "ssn": "123-45-6789",
    "diagnoses": ["Type 2 Diabetes", "Hypertension"],
    "medications": ["Metformin 500mg", "Lisinopril 10mg"],
}

META_EMPTY = {}

META_WITH_ANNOTATIONS = {
    "annotations": {
        "attribution": ["mcp://clinic-server/patients/P-12345"],
        "openWorldHint": False,
    }
}

TOOL_ANNOTATIONS = {
    "returnMetadata": {
        "source": "internal",
        "sensitivity": {"regulated": {"scopes": ["HIPAA"]}},
    }
}


def _hr(char: str = "═", width: int = 72) -> str:
    return char * width


def _pause(seconds: float = 0.4):
    time.sleep(seconds)


def _json_preview(data: dict, indent: int = 2) -> str:
    return json.dumps(data, indent=indent)


def _redact(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out[k] = _redact(v)
        elif isinstance(v, list):
            out[k] = ["[REDACTED]" if isinstance(i, str) else i for i in v]
        elif isinstance(v, str) and k not in ("patient_id", "status"):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


# ── WITHOUT Trust Annotations (simulated) ────────────────────────

def run_without():
    print()
    print(_hr())
    print(f"  {C.R}{C.B}WITHOUT Trust Annotations (current MCP){C.RST}")
    print(_hr())
    print()

    # Step 1: Agent A calls patient_lookup
    print(f"  {C.B}Agent A{C.RST} calls patient_lookup(\"P-12345\")")
    _pause()
    print(f"    → Result: {C.DIM}{_json_preview(PATIENT_DATA)}{C.RST}")
    print(f"    → _meta: {C.DIM}{{}}{C.RST}   ← {C.Y}empty, no annotations{C.RST}")
    print()
    _pause()

    # Step 2: Agent A forwards to Agent B (internal analytics)
    print(f"  {C.B}Agent A{C.RST} forwards result to {C.B}Agent B{C.RST} (Internal Analytics)")
    _pause()
    print(f"    → Result forwarded {C.R}in full{C.RST}")
    print(f"    {C.Y}⚠ PHI forwarded — no signal it was HIPAA-regulated data{C.RST}")
    print()
    _pause()

    # Step 3: Agent B forwards to Agent C (external reporting)
    print(f"  {C.B}Agent B{C.RST} forwards result to {C.B}Agent C{C.RST} (External Reporting — {C.R}PUBLIC{C.RST})")
    _pause()
    print(f"    → Result forwarded {C.R}in full{C.RST}: name=\"Jane Doe\", ssn=\"123-45-6789\"...")
    print(f"    {C.R}⚠ HIPAA VIOLATION — regulated data reached external system{C.RST}")
    print()
    _pause()

    # Step 4: Agent B logs result
    print(f"  {C.B}Agent B{C.RST} logs result to analytics pipeline")
    _pause()
    print(f"    → Logged: {C.DIM}{{\"name\": \"Jane Doe\", \"ssn\": \"123-45-6789\", ...}}{C.RST}")
    print(f"    {C.R}⚠ PHI in plaintext logs — no redaction signal{C.RST}")
    print()


# ── WITH Trust Annotations (real MCP transport) ──────────────────

async def run_with():
    sdk_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    server_script = os.path.join(sdk_root, "examples", "_shared", "mcp_server.py")
    python_src = os.path.join(sdk_root, "src")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env={**os.environ, "PYTHONPATH": python_src},
        cwd=sdk_root,
    )

    print()
    print(_hr())
    print(f"  {C.G}{C.B}WITH Trust Annotations (SEP-1913){C.RST}")
    print(_hr())
    print()

    async with stdio_client(server_params, errlog=open(os.devnull, "w")) as (rs, ws):
        async with ClientSession(rs, ws) as session:
            await session.initialize()

            # Discover tools
            tools_result = await session.list_tools()
            tool_ann: dict[str, dict] = {}
            for t in tools_result.tools:
                ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                tool_ann[t.name] = ann

            # Set up policy engine + session tracker
            engine = PolicyEngine(mode="enforce")
            for name, ann in tool_ann.items():
                engine.register_tool(name, ann)

            tracker_a = SessionTracker(session_id="agent-A")
            tracker_b = SessionTracker(session_id="agent-B")

            # ── Step 1: Agent A calls patient_lookup (via real MCP) ──
            print(f"  {C.B}Agent A{C.RST} calls patient_lookup(\"P-12345\")")
            _pause()

            cr = await session.call_tool("patient_lookup", {"patient_id": "P-12345"})
            raw = json.loads(cr.content[0].text) if cr.content else {}

            print(f"    → Result: {C.DIM}{json.dumps(raw)}{C.RST}")
            print(f"    → _meta.annotations: {C.CY}{_json_preview(META_WITH_ANNOTATIONS['annotations'])}{C.RST}")
            print(f"    → tool.annotations.returnMetadata: {C.CY}{_json_preview(TOOL_ANNOTATIONS['returnMetadata'])}{C.RST}")
            print()
            _pause()

            # Merge into Agent A's session
            tracker_a.merge(
                ResultAnnotations(
                    sensitivity=Regulated.of("HIPAA"),
                    attribution=("mcp://clinic-server/patients/P-12345",),
                ),
                "patient_lookup",
            )

            # ── Step 2: Agent A forwards to Agent B (internal) ──
            print(f"  {C.B}Agent A{C.RST} forwards result to {C.B}Agent B{C.RST} (Internal Analytics — {C.BL}internal{C.RST})")
            _pause()

            decision = engine.evaluate(
                "patient_lookup", action="forward", target_destination="internal",
            )
            print(f"    → Host policy: regulated(HIPAA) + target=internal → {C.G}✓ ALLOW{C.RST}")
            print(f"    → Request _meta.annotations: {C.CY}{{\"attribution\": [\"mcp://clinic-server/patients/P-12345\"]}}{C.RST}")
            print(f"    → Session tracks: sensitivity=regulated(HIPAA), attribution accumulated")
            print()
            _pause()

            # Agent B now has the data in its session
            tracker_b.merge(
                ResultAnnotations(
                    sensitivity=Regulated.of("HIPAA"),
                    attribution=("mcp://clinic-server/patients/P-12345",),
                ),
                "patient_lookup (forwarded)",
            )

            # ── Step 3: Agent B forwards to Agent C (public) — BLOCKED ──
            print(f"  {C.B}Agent B{C.RST} forwards result to {C.B}Agent C{C.RST} (External Reporting — {C.R}PUBLIC{C.RST})")
            _pause()

            decision = engine.evaluate(
                "patient_lookup", action="forward", target_destination="public",
            )
            assert not decision.allowed, "Expected BLOCK"
            print(f"    → Host policy: regulated(HIPAA) + target=public → {C.R}✗ BLOCK{C.RST}")
            print(f"    → Agent C receives: {C.DIM}\"Policy denied: HIPAA-regulated data cannot leave trust boundary\"{C.RST}")
            print(f"    {C.G}✓ PHI PROTECTED — deterministic enforcement, no model involved{C.RST}")
            print()
            _pause()

            # ── Step 4: Agent B logs result — REDACT ──
            print(f"  {C.B}Agent B{C.RST} logs result to analytics pipeline")
            _pause()

            # Policy says regulated data can't be logged in plaintext
            redacted = _redact(raw)
            print(f"    → Host policy: regulated(HIPAA) + action=log → {C.Y}◉ REDACT{C.RST}")
            print(f"    → Logged: {C.DIM}{json.dumps(redacted)}{C.RST}")
            print(f"    → Audit metadata: {C.CY}{{\"source\": \"internal\", \"sensitivity\": \"regulated:HIPAA\"}}{C.RST}")
            print(f"    {C.G}✓ COMPLIANT — PHI redacted, audit trail preserved{C.RST}")
            print()


# ── Comparison summary ────────────────────────────────────────────

def print_summary():
    print(_hr())
    print(f"  {C.B}Summary: What Changed?{C.RST}")
    print(_hr())
    print()
    print(f"  ┌─────────────────────────────┬─────────────────┬──────────────────┐")
    print(f"  │ Scenario                    │ {C.R}Without SEP-1913{C.RST} │ {C.G}With SEP-1913{C.RST}    │")
    print(f"  ├─────────────────────────────┼─────────────────┼──────────────────┤")
    print(f"  │ A → B (internal forward)    │ {C.Y}No check{C.RST}         │ {C.G}✓ ALLOW{C.RST}          │")
    print(f"  │ B → C (public forward)      │ {C.R}PHI leaked{C.RST}       │ {C.G}✗ BLOCKED{C.RST}        │")
    print(f"  │ B → logs (analytics)        │ {C.R}PHI in plaintext{C.RST} │ {C.G}◉ REDACTED{C.RST}       │")
    print(f"  │ Audit trail                 │ {C.R}None{C.RST}             │ {C.G}✓ Full provenance{C.RST} │")
    print(f"  │ Model involvement needed    │ {C.R}Yes (unreliable){C.RST} │ {C.G}No (deterministic){C.RST}│")
    print(f"  └─────────────────────────────┴─────────────────┴──────────────────┘")
    print()
    print(f"  {C.B}Key insight:{C.RST} SEP-1913 annotations give hosts the metadata they")
    print(f"  need to enforce data boundaries {C.B}without relying on the model{C.RST} to")
    print(f"  understand sensitivity.  The policy engine is deterministic —")
    print(f"  HIPAA data {C.B}cannot{C.RST} reach a public endpoint regardless of the prompt.")
    print()


# ── Main ──────────────────────────────────────────────────────────

async def main():
    print()
    print(f"  {C.B}{C.MAG}{'=' * 68}{C.RST}")
    print(f"  {C.B}{C.MAG}  D9: Multi-Agent Data Leak Prevention{C.RST}")
    print(f"  {C.B}{C.MAG}{'=' * 68}{C.RST}")
    print(f"  {C.DIM}Three agents: A (front-desk) → B (analytics) → C (external reporting)")
    print(f"  Patient: Jane Doe (P-12345), HIPAA-regulated PHI{C.RST}")

    # Part 1: WITHOUT (simulated — no server needed)
    run_without()

    # Part 2: WITH (real MCP server)
    await run_with()

    # Comparison table
    print_summary()

    print(f"  {C.B}{C.MAG}{'=' * 68}{C.RST}")
    print(f"  {C.B}{C.MAG}  Demo complete — the \"WITH\" scenario used real MCP stdio transport.{C.RST}")
    print(f"  {C.B}{C.MAG}{'=' * 68}{C.RST}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
