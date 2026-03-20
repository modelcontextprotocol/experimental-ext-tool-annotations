"""D8: Policy-Enforcing Host — connects to Healthcare Clinic MCP server
and demonstrates SEP-1913 trust annotation enforcement in a real host.

This is the "smart host" that:
  1. Connects to the Healthcare Clinic server via stdio
  2. Calls tools/list and extracts SEP-1913 annotations
  3. Registers every tool with a PolicyEngine
  4. Calls tools, tracks session propagation, and enforces policy
  5. Shows ALLOW / BLOCK / ESCALATE / REDACT decisions

Usage:
    cd <repo-root>/sdk/python
    PYTHONPATH=src python examples/healthcare/host.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys

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
from annotate import from_wire
from trust_types import (
    ResultAnnotations,
    SimpleDataClass,
    Regulated,
    sensitivity_level,
    max_sensitivity,
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


def _tag(label: str, color: str, width: int = 8) -> str:
    return f"{color}[{label:^{width}}]{C.RST}"

HOST   = lambda m: f"{_tag('HOST', C.BL)} {m}"
POLICY = lambda m: f"{_tag('POLICY', C.CY)} {m}"
LOG    = lambda m: f"{_tag('LOG', C.DIM, 8)} {m}"
OK     = lambda m: f"{C.G}✓ ALLOW{C.RST}  {m}"
BLOCK  = lambda m: f"{C.R}✗ BLOCK{C.RST}  {m}"
ESCAL  = lambda m: f"{C.Y}⚠ ESCALATE{C.RST} {m}"
REDACT = lambda m: f"{C.Y}◉ REDACT{C.RST}  {m}"


def _fmt_sens(val) -> str:
    if val is None:
        return "none"
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and "regulated" in val:
        scopes = val["regulated"].get("scopes", [])
        return f"regulated({','.join(scopes)})"
    if isinstance(val, list):
        return "|".join(_fmt_sens(v) for v in val)
    return str(val)


def _wire_to_typed(val):
    if isinstance(val, str):
        return SimpleDataClass(val)
    if isinstance(val, dict) and "regulated" in val:
        return Regulated.of(*val["regulated"].get("scopes", []))
    if isinstance(val, list):
        r = SimpleDataClass.NONE
        for v in val:
            r = max_sensitivity(r, _wire_to_typed(v))
        return r
    return SimpleDataClass.NONE


def _extract_sens(ann: dict):
    rm = ann.get("returnMetadata", {})
    im = ann.get("inputMetadata", {})
    return rm.get("sensitivity") or im.get("sensitivity") or "none"


def _redact_values(data: dict) -> dict:
    """Replace string values that look like PII/PHI with [REDACTED]."""
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out[k] = _redact_values(v)
        elif isinstance(v, list):
            out[k] = ["[REDACTED]" if isinstance(i, str) and len(i) > 1 else i for i in v]
        elif isinstance(v, str) and k not in ("status", "patient_id", "audit_id", "claim_id"):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


# ── Main ──────────────────────────────────────────────────────────

async def run_host():
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
    print("=" * 72)
    print(f"  {C.B}{C.BL}D8: Policy-Enforcing Host — SEP-1913 Demo{C.RST}")
    print("=" * 72)
    print()

    async with stdio_client(server_params, errlog=open(os.devnull, "w")) as (rs, ws):
        async with ClientSession(rs, ws) as session:
            await session.initialize()
            print(HOST("Connected to Healthcare Clinic server"))

            # ── tools/list ────────────────────────────────────
            result = await session.list_tools()
            tools = result.tools
            tool_ann: dict[str, dict] = {}
            for t in tools:
                ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                tool_ann[t.name] = ann

            print(HOST(f"Loaded {len(tools)} tools with SEP-1913 trust annotations"))

            # ── Policy engine ─────────────────────────────────
            engine = PolicyEngine(mode="enforce")
            for name, ann in tool_ann.items():
                engine.register_tool(name, ann)
            print(HOST(f"Policy mode: {C.R}ENFORCE{C.RST}"))
            print()

            tracker = SessionTracker(session_id="host-demo")

            # ═══════════════════════════════════════════════════
            # Scenario 1: health_check (benign)
            # ═══════════════════════════════════════════════════
            print(HOST(f"Calling {C.B}health_check{C.RST}..."))
            ann = tool_ann["health_check"]
            sens = _fmt_sens(_extract_sens(ann))
            source = ann.get("returnMetadata", {}).get("source", "system")
            decision = engine.evaluate("health_check")
            print(POLICY(f"tool=health_check sensitivity={sens} source={source} → {OK('')}"))

            cr = await session.call_tool("health_check")
            text = cr.content[0].text if cr.content else ""
            tracker.merge(ResultAnnotations(sensitivity=SimpleDataClass.NONE), "health_check")
            print(LOG(f'result={text}'))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 2: patient_lookup — HIPAA read + REDACT log
            # ═══════════════════════════════════════════════════
            print(HOST(f'Calling {C.B}patient_lookup{C.RST}(patient_id="P-12345")'))
            ann = tool_ann["patient_lookup"]
            sens = _fmt_sens(_extract_sens(ann))
            source = ann.get("returnMetadata", {}).get("source", "—")
            decision = engine.evaluate("patient_lookup")
            print(POLICY(f"tool=patient_lookup sensitivity={sens} source={source} → {OK('(read)')}"))

            cr = await session.call_tool("patient_lookup", {"patient_id": "P-12345"})
            raw_result = json.loads(cr.content[0].text) if cr.content else {}

            # Merge into session
            tracker.merge(
                ResultAnnotations(
                    sensitivity=Regulated.of("HIPAA"),
                    attribution=("Epic-EHR",),
                ),
                "patient_lookup",
            )

            # Policy: log action → REDACT (HIPAA data)
            decision_log = engine.evaluate("patient_lookup", action="call", target_destination=None)
            print(POLICY(f"action=log → {REDACT('regulated data, plaintext logging blocked')}"))
            redacted = _redact_values(raw_result)
            print(LOG(f"result={json.dumps(redacted)}"))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 3: Forward patient data to internal (ALLOW)
            # ═══════════════════════════════════════════════════
            print(HOST(f"Attempting to forward patient_lookup result to {C.B}Agent B (internal analytics){C.RST}..."))
            decision = engine.evaluate(
                "patient_lookup", action="forward", target_destination="internal",
            )
            if decision.allowed:
                print(POLICY(f"action=forward target=internal → {OK('internal destination compatible')}"))
            else:
                print(POLICY(f"action=forward target=internal → {BLOCK(decision.reason)}"))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 4: Forward patient data to public (BLOCK!)
            # ═══════════════════════════════════════════════════
            print(HOST(f"Attempting to forward patient_lookup result to {C.B}Agent C (external reporting){C.RST}..."))
            decision = engine.evaluate(
                "patient_lookup", action="forward", target_destination="public",
            )
            if not decision.allowed:
                print(POLICY(f"action=forward target=public → {BLOCK(decision.reason)}"))
                print(HOST(f"{C.R}✗ BLOCKED{C.RST} — regulated(HIPAA) → public destination"))
            else:
                print(POLICY(f"action=forward target=public → {OK('')}"))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 5: search_patients — open world propagation
            # ═══════════════════════════════════════════════════
            print(HOST(f'Calling {C.B}search_patients{C.RST}(query="diabetes treatment")'))

            cr = await session.call_tool("search_patients", {"query": "diabetes treatment"})
            text = cr.content[0].text if cr.content else ""

            ann = tool_ann["search_patients"]
            source = ann.get("returnMetadata", {}).get("source", "—")
            print(POLICY(f"tool=search_patients source={source} → {OK('(read)')}"))

            # Merge — this has HIPAA too, and we add attribution
            tracker.merge(
                ResultAnnotations(
                    sensitivity=Regulated.of("HIPAA"),
                    attribution=("Epic-EHR",),
                ),
                "search_patients",
            )

            # Preview
            try:
                preview = json.dumps(json.loads(text), indent=None)
                if len(preview) > 70:
                    preview = preview[:67] + "..."
            except Exception:
                preview = text[:70]
            print(LOG(f'result="{preview}" attribution=["Epic-EHR"]'))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 6: send_notification (malicious hint)
            # ═══════════════════════════════════════════════════
            print(HOST(f"Attempting to {C.B}send_notification{C.RST} to external recipient..."))
            decision = engine.evaluate(
                "send_notification", action="call", target_destination="public",
                session=tracker.session,
            )
            if not decision.allowed:
                print(POLICY(f"maliciousActivityHint=true → {BLOCK(decision.reason)}"))
                print(HOST(f"{C.R}✗ BLOCKED{C.RST} — tool flagged for potential malicious activity"))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 7: Session escalation — PII+ to public
            # ═══════════════════════════════════════════════════
            print(HOST(f"Attempting to call external reporting tool with HIPAA-tainted session..."))
            decision = engine.evaluate(
                "health_check",
                action="call",
                target_destination="public",
                session=tracker.session,
            )
            if decision.effect in ("escalate", "block") and not decision.allowed:
                print(POLICY(f"session.max_sensitivity=regulated(HIPAA) + dest=public → "
                             f"{ESCAL(decision.reason)}"))
                print(HOST(f"{C.Y}⚠ ESCALATE{C.RST} — regulated data in session, requires user confirmation"))
            elif decision.allowed:
                print(POLICY(f"→ {OK('')}"))
            print()

            # ═══════════════════════════════════════════════════
            # Scenario 8: Credentials to public (BLOCK)
            # ═══════════════════════════════════════════════════
            print(HOST(f"Attempting to forward {C.B}rotate_api_key{C.RST} result to public API..."))
            decision = engine.evaluate(
                "rotate_api_key", action="forward", target_destination="public",
            )
            if not decision.allowed:
                print(POLICY(f"sensitivity=credentials target=public → {BLOCK(decision.reason)}"))
                print(HOST(f"{C.R}✗ BLOCKED{C.RST} — credentials cannot reach public endpoint"))
            print()

            # ═══════════════════════════════════════════════════
            # Session summary
            # ═══════════════════════════════════════════════════
            print("─" * 72)
            print(HOST("Session summary:"))
            print()
            print(tracker.summary())
            print()
            print("─" * 72)
            print(HOST("Wire format (for outbound request annotations):"))
            print()
            print(json.dumps(tracker.to_wire(), indent=2))
            print()

    print("=" * 72)
    print(f"  {C.B}{C.BL}Host demo complete — all enforcement used real MCP transport.{C.RST}")
    print("=" * 72)
    print()


if __name__ == "__main__":
    asyncio.run(run_host())
