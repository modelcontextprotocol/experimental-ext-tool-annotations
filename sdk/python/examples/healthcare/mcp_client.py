"""MCP Client — connects to the Healthcare Clinic server and demonstrates
SEP-1913 trust annotations in action.

Performs:
  1. Connects to the server via stdio
  2. Lists all tools and extracts SEP-1913 annotations
  3. Calls each tool and tracks session propagation
  4. Applies policy enforcement (block/allow/escalate)
  5. Prints a full session summary

Usage:
    cd <repo-root>/sdk/python
    PYTHONPATH=src python examples/healthcare/mcp_client.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

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


# ── Helpers ───────────────────────────────────────────────────────

def _format_sensitivity(val) -> str:
    """Pretty-print a sensitivity value from wire format."""
    if val is None:
        return "none"
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and "regulated" in val:
        scopes = val["regulated"].get("scopes", [])
        return f"regulated({', '.join(scopes)})"
    if isinstance(val, list):
        return " | ".join(_format_sensitivity(v) for v in val)
    return str(val)


def _extract_sensitivity_from_wire(ann_dict: dict):
    """Extract the highest sensitivity DataClass from a wire-format annotations dict."""
    rm = ann_dict.get("returnMetadata", {})
    im = ann_dict.get("inputMetadata", {})
    sens = rm.get("sensitivity") or im.get("sensitivity") or "none"
    return sens


def _wire_sensitivity_to_typed(val):
    """Convert wire sensitivity to typed DataClass."""
    if isinstance(val, str):
        return SimpleDataClass(val)
    if isinstance(val, dict) and "regulated" in val:
        scopes = val["regulated"].get("scopes", [])
        return Regulated.of(*scopes)
    if isinstance(val, list):
        result = SimpleDataClass.NONE
        for v in val:
            result = max_sensitivity(result, _wire_sensitivity_to_typed(v))
        return result
    return SimpleDataClass.NONE


# ── Colors (ANSI) ────────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"


def _ok(msg: str) -> str:
    return f"{C.GREEN}✓ {msg}{C.RESET}"

def _blocked(msg: str) -> str:
    return f"{C.RED}✗ BLOCKED{C.RESET} — {msg}"

def _escalate(msg: str) -> str:
    return f"{C.YELLOW}⚠ ESCALATE{C.RESET} — {msg}"

def _warn(msg: str) -> str:
    return f"{C.YELLOW}⚠ WARN{C.RESET} — {msg}"

def _info(msg: str) -> str:
    return f"{C.CYAN}ℹ {msg}{C.RESET}"

def _header(msg: str) -> str:
    return f"{C.BOLD}{C.BLUE}{msg}{C.RESET}"


# ── Main client logic ────────────────────────────────────────────

async def run_client():
    sdk_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    server_script = os.path.join(sdk_root, "examples", "_shared", "mcp_server.py")
    python_src = os.path.join(sdk_root, "src")

    # Build env with PYTHONPATH so server can import from src/
    env = {**os.environ, "PYTHONPATH": python_src}

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=env,
        cwd=sdk_root,
    )

    print()
    print("=" * 70)
    print(_header("  MCP Client — SEP-1913 Trust Annotations Demo"))
    print("=" * 70)
    print()

    async with stdio_client(server_params, errlog=open(os.devnull, "w")) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the session
            await session.initialize()
            print(_info("Connected to Healthcare Clinic server"))
            print()

            # ── Step 1: List tools ────────────────────────────
            print(_header("─── Step 1: tools/list — Discover tools & SEP-1913 annotations ───"))
            print()

            result = await session.list_tools()
            tools = result.tools

            print(f"  Found {len(tools)} tools:\n")
            tool_annotations: dict[str, dict] = {}

            for tool in tools:
                ann_dict = {}
                if tool.annotations:
                    ann_dict = tool.annotations.model_dump(exclude_none=True)
                tool_annotations[tool.name] = ann_dict

                sens_raw = _extract_sensitivity_from_wire(ann_dict)
                sens_str = _format_sensitivity(sens_raw)
                source = ann_dict.get("returnMetadata", {}).get("source", "—")
                dest = ann_dict.get("inputMetadata", {}).get("destination", "—")
                malicious = ann_dict.get("maliciousActivityHint", False)

                flags = []
                if malicious:
                    flags.append(f"{C.RED}⚡malicious{C.RESET}")
                if ann_dict.get("readOnlyHint"):
                    flags.append("readonly")
                if ann_dict.get("destructiveHint"):
                    flags.append(f"{C.YELLOW}destructive{C.RESET}")

                flag_str = f"  [{', '.join(flags)}]" if flags else ""
                print(f"  {C.BOLD}{tool.name:30s}{C.RESET}  "
                      f"sensitivity={sens_str:20s}  source={str(source):18s}  "
                      f"dest={str(dest)}{flag_str}")

            print()

            # ── Step 2: Set up policy engine ──────────────────
            print(_header("─── Step 2: Initialize policy engine (enforce mode) ───"))
            print()

            engine = PolicyEngine(mode="enforce")
            for name, ann in tool_annotations.items():
                engine.register_tool(name, ann)
            print(f"  Registered {len(tool_annotations)} tools with policy engine")
            print(f"  Mode: {C.RED}ENFORCE{C.RESET} (blocks violating calls)")
            print()

            # ── Step 3: Call tools + track session ────────────
            print(_header("─── Step 3: Call tools & track session propagation ───"))
            print()

            tracker = SessionTracker(session_id="client-demo-001")

            # Call sequence
            calls = [
                ("health_check", {}),
                ("patient_lookup", {"patient_id": "P-12345"}),
                ("staff_directory", {"department": "Cardiology"}),
                ("process_insurance_claim", {"patient_id": "P-12345", "amount": 1500.0, "code": "99213"}),
                ("rotate_api_key", {"service": "lab-integration"}),
            ]

            for tool_name, args in calls:
                print(f"  {C.BOLD}Calling {tool_name}{C.RESET}({_format_args(args)})...")

                call_result = await session.call_tool(tool_name, args)

                # Extract text content from result
                content_text = ""
                for content in call_result.content:
                    if hasattr(content, "text"):
                        content_text = content.text
                        break

                # Parse the result to show a preview
                try:
                    result_data = json.loads(content_text)
                    preview = json.dumps(result_data, indent=None)
                    if len(preview) > 80:
                        preview = preview[:77] + "..."
                except (json.JSONDecodeError, TypeError):
                    preview = content_text[:80] if content_text else "(empty)"

                print(f"    Result: {C.DIM}{preview}{C.RESET}")

                # Merge into session tracker
                ann = tool_annotations.get(tool_name, {})
                sens_raw = _extract_sensitivity_from_wire(ann)
                typed_sens = _wire_sensitivity_to_typed(sens_raw)
                attribution = tuple(ann.get("attribution", []))

                result_ann = ResultAnnotations(
                    sensitivity=typed_sens,
                    attribution=attribution,
                    malicious_activity_hint=ann.get("maliciousActivityHint", False),
                    open_world_hint=ann.get("openWorldHint", False),
                )
                tracker.merge(result_ann, tool_name)

                print(f"    Session: max_sensitivity={tracker.session.max_sensitivity}, "
                      f"attribution={sorted(tracker.session.attribution)}")
                print()

            # ── Step 4: Policy enforcement scenarios ──────────
            print(_header("─── Step 4: Policy enforcement scenarios ───"))
            print()

            scenarios = [
                {
                    "desc": "Forward patient data to internal analytics",
                    "tool": "patient_lookup",
                    "action": "call",
                    "dest": "internal",
                },
                {
                    "desc": "Forward patient data to PUBLIC endpoint",
                    "tool": "patient_lookup",
                    "action": "call",
                    "dest": "public",
                },
                {
                    "desc": "Send notification (malicious hint) with HIPAA session",
                    "tool": "send_notification",
                    "action": "call",
                    "dest": "public",
                },
                {
                    "desc": "Forward credentials externally",
                    "tool": "rotate_api_key",
                    "action": "call",
                    "dest": "public",
                },
                {
                    "desc": "Read health check (benign)",
                    "tool": "health_check",
                    "action": "call",
                    "dest": None,
                },
            ]

            for scenario in scenarios:
                decision = engine.evaluate(
                    tool=scenario["tool"],
                    action=scenario["action"],
                    target_destination=scenario["dest"],
                    session=tracker.session,
                )

                status_str = ""
                if not decision.allowed:
                    status_str = _blocked(decision.reason)
                elif decision.effect == "escalate":
                    status_str = _escalate(decision.reason)
                elif decision.effect == "warn":
                    status_str = _warn(decision.reason)
                else:
                    status_str = _ok("ALLOWED")

                dest_str = scenario['dest'] or 'any'
                print(f"  Scenario: {scenario['desc']}")
                print(f"    {scenario['tool']} → {dest_str}")
                print(f"    {status_str}")
                print()

            # ── Step 5: Session summary ───────────────────────
            print(_header("─── Step 5: Session summary ───"))
            print()
            print(tracker.summary())
            print()

            # ── Step 6: Wire format ───────────────────────────
            print(_header("─── Step 6: Wire format (session state for outbound propagation) ───"))
            print()
            print(json.dumps(tracker.to_wire(), indent=2))
            print()

    print("=" * 70)
    print(_header("  Demo complete — all calls used real MCP stdio transport."))
    print("=" * 70)
    print()


def _format_args(args: dict) -> str:
    """Format call arguments for display."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


if __name__ == "__main__":
    asyncio.run(run_client())
