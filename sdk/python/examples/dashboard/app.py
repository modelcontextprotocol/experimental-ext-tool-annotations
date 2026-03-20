"""SEP-1913 Trust Annotations Test Dashboard.

Web-based UI for testers to:
  1. View all server tools and their SEP-1913 trust annotations
  2. Run single-client demo scenarios (mcp_client.py equivalent)
  3. Run multi-agent data leak prevention scenarios
  4. Execute policy enforcement tests interactively
  5. View session propagation state in real time

Usage:
    cd <repo-root>/sdk/python
    PYTHONPATH=src python examples/dashboard/app.py

Opens at http://localhost:8913
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import traceback

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from policy import PolicyEngine
from propagate import SessionTracker
from annotate import from_wire, to_wire
from trust_types import (
    ResultAnnotations,
    SessionAnnotations,
    SimpleDataClass,
    Regulated,
    TrustAnnotations,
    InputMetadata,
    ReturnMetadata,
    Source,
    Destination,
    Outcome,
    sensitivity_level,
    max_sensitivity,
)

SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER_SCRIPT = os.path.join(SDK_ROOT, "examples", "_shared", "mcp_server.py")
PYTHON_SRC = os.path.join(SDK_ROOT, "src")


# ── Helpers ───────────────────────────────────────────────────────

def _strip_ansi(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _fmt_sensitivity(val) -> str:
    if val is None:
        return "none"
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and "regulated" in val:
        scopes = val["regulated"].get("scopes", [])
        return f"regulated({', '.join(scopes)})"
    if isinstance(val, list):
        return " | ".join(_fmt_sensitivity(v) for v in val)
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


def _server_params():
    return StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env={**os.environ, "PYTHONPATH": PYTHON_SRC},
        cwd=SDK_ROOT,
    )


# ── API Endpoints ─────────────────────────────────────────────────

async def api_tools(request):
    """List all tools with full SEP-1913 annotations."""
    try:
        async with stdio_client(_server_params(), errlog=open(os.devnull, "w")) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = []
                for t in result.tools:
                    ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                    sens_raw = _extract_sens(ann)
                    tools.append({
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                        "annotations": ann,
                        "sensitivity": _fmt_sensitivity(sens_raw),
                        "source": ann.get("returnMetadata", {}).get("source", "—"),
                        "destination": ann.get("inputMetadata", {}).get("destination", "—"),
                        "outcomes": ann.get("inputMetadata", {}).get("outcomes", "—"),
                        "attribution": ann.get("attribution", []),
                        "maliciousActivityHint": ann.get("maliciousActivityHint", False),
                        "readOnlyHint": ann.get("readOnlyHint", False),
                        "destructiveHint": ann.get("destructiveHint", False),
                        "openWorldHint": ann.get("openWorldHint", False),
                    })
                return JSONResponse({"tools": tools})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_call_tool(request):
    """Call a single tool and return result + annotations."""
    body = await request.json()
    tool_name = body.get("tool")
    args = body.get("args", {})

    try:
        async with stdio_client(_server_params(), errlog=open(os.devnull, "w")) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                cr = await session.call_tool(tool_name, args)
                text = cr.content[0].text if cr.content else ""
                try:
                    result_data = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    result_data = {"raw": text}
                return JSONResponse({"tool": tool_name, "args": args, "result": result_data})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_run_single_client(request):
    """Run the single-client demo (mcp_client.py equivalent)."""
    steps = []
    try:
        async with stdio_client(_server_params(), errlog=open(os.devnull, "w")) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                steps.append({"step": "connect", "status": "ok", "message": "Connected to Healthcare Clinic server"})

                # Step 1: List tools
                result = await session.list_tools()
                tool_ann = {}
                tool_list = []
                for t in result.tools:
                    ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                    tool_ann[t.name] = ann
                    tool_list.append({
                        "name": t.name,
                        "sensitivity": _fmt_sensitivity(_extract_sens(ann)),
                        "source": ann.get("returnMetadata", {}).get("source", "—"),
                        "destination": ann.get("inputMetadata", {}).get("destination", "—"),
                    })
                steps.append({"step": "list_tools", "status": "ok", "tools": tool_list})

                # Step 2: Policy engine
                engine = PolicyEngine(mode="enforce")
                for name, ann in tool_ann.items():
                    engine.register_tool(name, ann)
                steps.append({"step": "policy_init", "status": "ok", "mode": "enforce", "tools_registered": len(tool_ann)})

                # Step 3: Call tools + track session
                tracker = SessionTracker(session_id="dashboard-single-client")
                calls = [
                    ("health_check", {}),
                    ("patient_lookup", {"patient_id": "P-12345"}),
                    ("staff_directory", {"department": "Cardiology"}),
                    ("process_insurance_claim", {"patient_id": "P-12345", "amount": 1500.0, "code": "99213"}),
                    ("rotate_api_key", {"service": "lab-integration"}),
                ]

                call_results = []
                for tool_name, args in calls:
                    cr = await session.call_tool(tool_name, args)
                    text = cr.content[0].text if cr.content else ""
                    try:
                        result_data = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {"raw": text}

                    ann = tool_ann.get(tool_name, {})
                    sens_raw = _extract_sens(ann)
                    typed_sens = _wire_to_typed(sens_raw)
                    attribution = tuple(ann.get("attribution", []))

                    result_ann = ResultAnnotations(
                        sensitivity=typed_sens,
                        attribution=attribution,
                        malicious_activity_hint=ann.get("maliciousActivityHint", False),
                        open_world_hint=ann.get("openWorldHint", False),
                    )
                    tracker.merge(result_ann, tool_name)

                    call_results.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result_data,
                        "session_sensitivity": str(tracker.session.max_sensitivity),
                        "session_attribution": sorted(tracker.session.attribution),
                    })

                steps.append({"step": "call_tools", "status": "ok", "calls": call_results})

                # Step 4: Policy enforcement scenarios
                scenarios = [
                    {"desc": "Forward patient data to internal analytics", "tool": "patient_lookup", "dest": "internal"},
                    {"desc": "Forward patient data to PUBLIC endpoint", "tool": "patient_lookup", "dest": "public"},
                    {"desc": "Send notification (malicious hint) with HIPAA session", "tool": "send_notification", "dest": "public"},
                    {"desc": "Forward credentials externally", "tool": "rotate_api_key", "dest": "public"},
                    {"desc": "Read health check (benign)", "tool": "health_check", "dest": None},
                ]

                policy_results = []
                for sc in scenarios:
                    decision = engine.evaluate(
                        tool=sc["tool"], action="call",
                        target_destination=sc["dest"],
                        session=tracker.session,
                    )
                    policy_results.append({
                        "description": sc["desc"],
                        "tool": sc["tool"],
                        "destination": sc["dest"] or "any",
                        "allowed": decision.allowed,
                        "effect": decision.effect,
                        "rule": decision.rule,
                        "reason": decision.reason,
                    })
                steps.append({"step": "policy_enforcement", "status": "ok", "scenarios": policy_results})

                # Step 5: Session summary
                steps.append({
                    "step": "session_summary",
                    "status": "ok",
                    "summary": _strip_ansi(tracker.summary()),
                    "wire_format": tracker.to_wire(),
                })

        return JSONResponse({"status": "ok", "steps": steps})
    except Exception as e:
        steps.append({"step": "error", "status": "error", "message": str(e), "traceback": traceback.format_exc()})
        return JSONResponse({"status": "error", "steps": steps}, status_code=500)


async def api_run_multi_agent(request):
    """Run the multi-agent data leak prevention scenario."""
    results = {"without_annotations": [], "with_annotations": []}

    # ── Part 1: WITHOUT Trust Annotations (simulated) ──
    patient_data = {
        "patient_id": "P-12345", "name": "Jane Doe", "dob": "1985-03-15",
        "ssn": "123-45-6789", "diagnoses": ["Type 2 Diabetes", "Hypertension"],
        "medications": ["Metformin 500mg", "Lisinopril 10mg"],
    }

    results["without_annotations"] = [
        {"agent": "A", "action": "patient_lookup('P-12345')", "result": "Full PHI returned",
         "data_preview": patient_data, "status": "ok", "issue": None},
        {"agent": "A→B", "action": "Forward to Internal Analytics", "result": "PHI forwarded in full",
         "data_preview": patient_data, "status": "warning", "issue": "No signal it was HIPAA-regulated"},
        {"agent": "B→C", "action": "Forward to External Reporting (PUBLIC)",
         "result": "PHI forwarded in full — HIPAA VIOLATION",
         "data_preview": {"name": "Jane Doe", "ssn": "123-45-6789"}, "status": "danger",
         "issue": "Regulated data reached external system"},
        {"agent": "B", "action": "Log to analytics pipeline", "result": "PHI in plaintext logs",
         "data_preview": {"name": "Jane Doe", "ssn": "123-45-6789"}, "status": "danger",
         "issue": "No redaction signal"},
    ]

    # ── Part 2: WITH Trust Annotations (real MCP) ──
    try:
        async with stdio_client(_server_params(), errlog=open(os.devnull, "w")) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_ann = {}
                for t in tools_result.tools:
                    ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                    tool_ann[t.name] = ann

                engine = PolicyEngine(mode="enforce")
                for name, ann in tool_ann.items():
                    engine.register_tool(name, ann)

                tracker_a = SessionTracker(session_id="agent-A")
                tracker_b = SessionTracker(session_id="agent-B")

                # Step 1: Agent A calls patient_lookup
                cr = await session.call_tool("patient_lookup", {"patient_id": "P-12345"})
                raw = json.loads(cr.content[0].text) if cr.content else {}

                tracker_a.merge(
                    ResultAnnotations(sensitivity=Regulated.of("HIPAA"), attribution=("Epic-EHR",)),
                    "patient_lookup",
                )

                results["with_annotations"].append({
                    "agent": "A", "action": "patient_lookup('P-12345')",
                    "result": "PHI returned with trust metadata",
                    "data_preview": raw,
                    "trust_metadata": {
                        "returnMetadata": {"source": "internal", "sensitivity": "regulated(HIPAA)"},
                        "attribution": ["Epic-EHR"],
                    },
                    "status": "ok", "issue": None,
                })

                # Step 2: A → B (internal) — ALLOW
                decision_ab = engine.evaluate("patient_lookup", action="forward", target_destination="internal")
                tracker_b.merge(
                    ResultAnnotations(sensitivity=Regulated.of("HIPAA"), attribution=("Epic-EHR",)),
                    "patient_lookup (forwarded)",
                )

                results["with_annotations"].append({
                    "agent": "A→B", "action": "Forward to Internal Analytics",
                    "result": f"{'ALLOWED' if decision_ab.allowed else 'BLOCKED'} — internal destination compatible",
                    "policy_decision": {
                        "allowed": decision_ab.allowed, "effect": decision_ab.effect,
                        "rule": decision_ab.rule, "reason": decision_ab.reason,
                    },
                    "status": "ok", "issue": None,
                })

                # Step 3: B → C (public) — BLOCKED
                decision_bc = engine.evaluate("patient_lookup", action="forward", target_destination="public")

                results["with_annotations"].append({
                    "agent": "B→C", "action": "Forward to External Reporting (PUBLIC)",
                    "result": f"{'ALLOWED' if decision_bc.allowed else 'BLOCKED'} — regulated(HIPAA) cannot reach public",
                    "policy_decision": {
                        "allowed": decision_bc.allowed, "effect": decision_bc.effect,
                        "rule": decision_bc.rule, "reason": decision_bc.reason,
                    },
                    "status": "success" if not decision_bc.allowed else "danger",
                    "issue": None if not decision_bc.allowed else "Should have been blocked!",
                })

                # Step 4: B logs — REDACT
                redacted = _redact_values(raw)
                results["with_annotations"].append({
                    "agent": "B", "action": "Log to analytics pipeline",
                    "result": "REDACTED — regulated data, plaintext logging blocked",
                    "data_preview": redacted,
                    "status": "success", "issue": None,
                })

                results["session_state"] = {
                    "agent_a": {"sensitivity": str(tracker_a.session.max_sensitivity),
                                "attribution": sorted(tracker_a.session.attribution)},
                    "agent_b": {"sensitivity": str(tracker_b.session.max_sensitivity),
                                "attribution": sorted(tracker_b.session.attribution)},
                }

        return JSONResponse({"status": "ok", "results": results})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e), "results": results}, status_code=500)


async def api_run_host_scenarios(request):
    """Run all host policy enforcement scenarios."""
    scenarios = []
    try:
        async with stdio_client(_server_params(), errlog=open(os.devnull, "w")) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_ann = {}
                for t in tools_result.tools:
                    ann = t.annotations.model_dump(exclude_none=True) if t.annotations else {}
                    tool_ann[t.name] = ann

                engine = PolicyEngine(mode="enforce")
                for name, ann in tool_ann.items():
                    engine.register_tool(name, ann)

                tracker = SessionTracker(session_id="host-dashboard")

                # Run through all tools to build session state
                tool_calls = [
                    ("health_check", {}),
                    ("patient_lookup", {"patient_id": "P-12345"}),
                    ("search_patients", {"query": "diabetes"}),
                    ("staff_directory", {}),
                    ("process_insurance_claim", {"patient_id": "P-12345", "amount": 1500.0, "code": "99213"}),
                    ("rotate_api_key", {"service": "lab-integration"}),
                ]

                for tool_name, args in tool_calls:
                    cr = await session.call_tool(tool_name, args)
                    text = cr.content[0].text if cr.content else ""
                    try:
                        result_data = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {"raw": text}

                    ann = tool_ann.get(tool_name, {})
                    typed_sens = _wire_to_typed(_extract_sens(ann))
                    tracker.merge(
                        ResultAnnotations(
                            sensitivity=typed_sens,
                            attribution=tuple(ann.get("attribution", [])),
                            malicious_activity_hint=ann.get("maliciousActivityHint", False),
                            open_world_hint=ann.get("openWorldHint", False),
                        ),
                        tool_name,
                    )

                # Policy evaluation scenarios
                policy_scenarios = [
                    {"desc": "health_check (benign read)", "tool": "health_check", "dest": None,
                     "category": "Basic"},
                    {"desc": "patient_lookup read (HIPAA)", "tool": "patient_lookup", "dest": None,
                     "category": "HIPAA"},
                    {"desc": "Forward patient data → internal", "tool": "patient_lookup", "dest": "internal",
                     "category": "HIPAA"},
                    {"desc": "Forward patient data → public", "tool": "patient_lookup", "dest": "public",
                     "category": "HIPAA"},
                    {"desc": "Forward credentials → public", "tool": "rotate_api_key", "dest": "public",
                     "category": "Credentials"},
                    {"desc": "send_notification (malicious hint)", "tool": "send_notification", "dest": "public",
                     "category": "Malicious"},
                    {"desc": "send_notification → internal", "tool": "send_notification", "dest": "internal",
                     "category": "Malicious"},
                    {"desc": "process_insurance_claim (financial)", "tool": "process_insurance_claim", "dest": None,
                     "category": "Financial"},
                    {"desc": "Forward insurance claim → public", "tool": "process_insurance_claim", "dest": "public",
                     "category": "Financial"},
                    {"desc": "staff_directory (PII) → public", "tool": "staff_directory", "dest": "public",
                     "category": "PII"},
                ]

                for sc in policy_scenarios:
                    decision = engine.evaluate(
                        tool=sc["tool"], action="call",
                        target_destination=sc["dest"],
                        session=tracker.session,
                    )
                    scenarios.append({
                        "description": sc["desc"],
                        "category": sc["category"],
                        "tool": sc["tool"],
                        "destination": sc["dest"] or "any",
                        "allowed": decision.allowed,
                        "effect": decision.effect,
                        "rule": decision.rule,
                        "reason": decision.reason,
                    })

                return JSONResponse({
                    "status": "ok",
                    "scenarios": scenarios,
                    "session": {
                        "sensitivity": str(tracker.session.max_sensitivity),
                        "attribution": sorted(tracker.session.attribution),
                        "open_world_hint": tracker.session.open_world_hint,
                        "malicious_activity_hint": tracker.session.malicious_activity_hint,
                        "call_count": tracker.call_count,
                    },
                    "wire_format": tracker.to_wire(),
                })
    except BaseException as e:
        detail = str(e)
        if hasattr(e, 'exceptions'):
            detail = "; ".join(str(sub) for sub in e.exceptions)
        return JSONResponse({"status": "error", "error": detail, "traceback": traceback.format_exc()}, status_code=500)


async def api_run_usability_tests(request):
    """Run pytest usability scenario tests and return results."""
    import subprocess
    test_file = os.path.join(SDK_ROOT, "tests", "test_usability_scenarios.py")
    env = {**os.environ, "PYTHONPATH": os.path.join(SDK_ROOT, "src")}

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "--no-header"],
        capture_output=True, text=True, env=env, cwd=SDK_ROOT,
        timeout=60,
    )

    lines = proc.stdout.strip().split("\n")
    tests = []
    for line in lines:
        if "::" in line and ("PASSED" in line or "FAILED" in line or "ERROR" in line):
            parts = line.strip().split("::")
            status = "passed" if "PASSED" in line else "failed" if "FAILED" in line else "error"
            test_path = "::".join(parts[1:]).split(" ")[0] if len(parts) > 1 else line
            class_name = parts[1] if len(parts) > 1 else ""
            test_name = parts[2].split(" ")[0] if len(parts) > 2 else ""
            # Extract scenario number from class name
            scenario_match = re.search(r"Scenario(\d+)", class_name)
            scenario_num = int(scenario_match.group(1)) if scenario_match else 0
            tests.append({
                "scenario": scenario_num,
                "class": class_name,
                "test": test_name,
                "status": status,
                "line": _strip_ansi(line.strip()),
            })

    # Summary line
    summary = ""
    for line in reversed(lines):
        if "passed" in line or "failed" in line:
            summary = _strip_ansi(line.strip())
            break

    return JSONResponse({
        "status": "ok" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "tests": tests,
        "summary": summary,
        "stdout": _strip_ansi(proc.stdout),
        "stderr": _strip_ansi(proc.stderr),
    })


# ── HTML Dashboard ────────────────────────────────────────────────

async def homepage(request):
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ── App ───────────────────────────────────────────────────────────

app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/api/tools", api_tools),
        Route("/api/call-tool", api_call_tool, methods=["POST"]),
        Route("/api/run/single-client", api_run_single_client, methods=["POST"]),
        Route("/api/run/multi-agent", api_run_multi_agent, methods=["POST"]),
        Route("/api/run/host-scenarios", api_run_host_scenarios, methods=["POST"]),
        Route("/api/run/usability-tests", api_run_usability_tests, methods=["POST"])
    ],
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DASHBOARD_PORT", "8913"))
    print(f"\n  SEP-1913 Trust Annotations Test Dashboard")
    print(f"  http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
