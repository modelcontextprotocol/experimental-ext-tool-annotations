"""Healthcare Clinic — Real MCP Server with SEP-1913 trust annotations.

Runs as a stdio MCP server using the official MCP Python SDK (FastMCP).
Every tool carries SEP-1913 trust annotations via ToolAnnotations extra fields.

Usage:
    # Run directly (stdio transport):
    PYTHONPATH=sdk/python/src python sdk/python/examples/_shared/mcp_server.py

    # Or via the client:
    PYTHONPATH=sdk/python/src python sdk/python/examples/healthcare/mcp_client.py
"""

from __future__ import annotations

import sys
import os

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from mcp.server import FastMCP
from mcp.types import ToolAnnotations

from trust_types import (
    Destination,
    InputMetadata,
    Outcome,
    Regulated,
    ReturnMetadata,
    SimpleDataClass,
    Source,
    TrustAnnotations,
)
from annotate import to_wire


# ===================================================================
# In-memory data stores (shared across the server session)
# ===================================================================

PATIENTS: dict[str, dict] = {
    "P-12345": {
        "name": "Jane Doe",
        "dob": "1985-03-15",
        "ssn": "***-**-6789",
        "diagnoses": ["Type 2 Diabetes", "Hypertension"],
        "medications": ["Metformin 500mg", "Lisinopril 10mg"],
    },
    "P-67890": {
        "name": "John Smith",
        "dob": "1972-11-02",
        "ssn": "***-**-1234",
        "diagnoses": ["Asthma"],
        "medications": ["Albuterol inhaler"],
    },
}

CLAIMS: list[dict] = []
NOTIFICATIONS: list[dict] = []
_audit_counter = 0
_claim_counter = 0
_msg_counter = 0


def _next_audit_id() -> str:
    global _audit_counter
    _audit_counter += 1
    return f"AUD-{_audit_counter:05d}"


def _next_claim_id() -> str:
    global _claim_counter
    _claim_counter += 1
    return f"CLM-{_claim_counter:05d}"


def _next_msg_id() -> str:
    global _msg_counter
    _msg_counter += 1
    return f"MSG-{_msg_counter:05d}"


def _make_annotations(
    *,
    read_only: bool = False,
    destructive: bool = False,
    open_world: bool = False,
    trust: TrustAnnotations | None = None,
) -> ToolAnnotations:
    """Build ToolAnnotations with standard MCP hints + SEP-1913 extensions."""
    base = {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "openWorldHint": open_world,
    }
    if trust:
        base.update(to_wire(trust))
    return ToolAnnotations(**base)


# ===================================================================
# Server
# ===================================================================

server = FastMCP(
    "Healthcare Clinic",
    instructions=(
        "A healthcare clinic MCP server with SEP-1913 trust annotations. "
        "Tools dealing with patient data are HIPAA-regulated. "
        "Always check tool annotations before forwarding results."
    ),
)


# ── Tool 1: health_check ──────────────────────────────────────────

@server.tool(
    name="health_check",
    description="Returns server health status. No sensitive data involved.",
    annotations=_make_annotations(read_only=True),
)
def health_check() -> dict:
    return {"status": "ok", "uptime_seconds": 86400, "version": "1.2.0"}


# ── Tool 2: patient_lookup ────────────────────────────────────────

@server.tool(
    name="patient_lookup",
    description="Look up a patient by ID. Returns HIPAA-regulated PHI.",
    annotations=_make_annotations(
        read_only=True,
        trust=TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
            attribution=("Epic-EHR",),
        ),
    ),
)
def patient_lookup(patient_id: str) -> dict:
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return {"error": f"Patient {patient_id} not found"}
    return {"patient_id": patient_id, **patient}


# ── Tool 3: search_patients ──────────────────────────────────────

@server.tool(
    name="search_patients",
    description="Search patients by name or diagnosis. Returns HIPAA-regulated PHI.",
    annotations=_make_annotations(
        read_only=True,
        trust=TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
            ),
            attribution=("Epic-EHR",),
        ),
    ),
)
def search_patients(query: str, limit: int = 10) -> dict:
    q = query.lower()
    results = []
    for pid, rec in PATIENTS.items():
        if (
            q in pid.lower()
            or q in rec["name"].lower()
            or any(q in d.lower() for d in rec.get("diagnoses", []))
        ):
            results.append({"patient_id": pid, "name": rec["name"]})
    return {"results": results[:limit], "total": len(results)}


# ── Tool 4: update_patient_record ────────────────────────────────

@server.tool(
    name="update_patient_record",
    description="Update a patient record field. Writes HIPAA-regulated PHI.",
    annotations=_make_annotations(
        destructive=True,
        trust=TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=Regulated.of("HIPAA"),
                outcomes=Outcome.CONSEQUENTIAL,
            ),
            attribution=("Epic-EHR",),
        ),
    ),
)
def update_patient_record(patient_id: str, field: str, value: str) -> dict:
    patient = PATIENTS.get(patient_id)
    if patient is None:
        return {"error": f"Patient {patient_id} not found"}
    allowed_fields = {"name", "dob", "diagnoses", "medications"}
    if field not in allowed_fields:
        return {"error": f"Field '{field}' is not updatable. Allowed: {sorted(allowed_fields)}"}
    if field in ("diagnoses", "medications"):
        # Append to list fields
        patient[field].append(value)
    else:
        patient[field] = value
    return {
        "patient_id": patient_id,
        "field": field,
        "new_value": patient[field],
        "status": "updated",
        "audit_id": _next_audit_id(),
    }


# ── Tool 5: staff_directory ──────────────────────────────────────

@server.tool(
    name="staff_directory",
    description="List clinic staff. Contains PII (names, emails, phone numbers).",
    annotations=_make_annotations(
        read_only=True,
        trust=TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.PII,
            ),
        ),
    ),
)
def staff_directory(department: str = "") -> dict:
    staff = [
        {"name": "Dr. Sarah Chen", "email": "s.chen@clinic.org",
         "phone": "555-0101", "department": "Cardiology"},
        {"name": "Nurse Mike Johnson", "email": "m.johnson@clinic.org",
         "phone": "555-0102", "department": "Emergency"},
    ]
    if department:
        staff = [s for s in staff if s["department"].lower() == department.lower()]
    return {"staff": staff}


# ── Tool 6: process_insurance_claim ──────────────────────────────

@server.tool(
    name="process_insurance_claim",
    description="Submit an insurance claim. Financial data + patient reference.",
    annotations=_make_annotations(
        trust=TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.INTERNAL,
                sensitivity=SimpleDataClass.FINANCIAL,
            ),
            input_metadata=InputMetadata(
                destination=Destination.INTERNAL,
                sensitivity=SimpleDataClass.FINANCIAL,
                outcomes=Outcome.CONSEQUENTIAL,
            ),
        ),
    ),
)
def process_insurance_claim(patient_id: str, amount: float, code: str) -> dict:
    if patient_id not in PATIENTS:
        return {"error": f"Patient {patient_id} not found"}
    claim = {
        "claim_id": _next_claim_id(),
        "patient_id": patient_id,
        "patient_name": PATIENTS[patient_id]["name"],
        "amount": amount,
        "procedure_code": code,
        "status": "submitted",
    }
    CLAIMS.append(claim)
    return claim


# ── Tool 7: rotate_api_key ──────────────────────────────────────

@server.tool(
    name="rotate_api_key",
    description="Rotate an API key for an external service. Returns credentials.",
    annotations=_make_annotations(
        trust=TrustAnnotations(
            return_metadata=ReturnMetadata(
                source=Source.SYSTEM,
                sensitivity=SimpleDataClass.CREDENTIALS,
            ),
        ),
    ),
)
def rotate_api_key(service: str) -> dict:
    return {
        "service": service,
        "new_key": "sk-REDACTED-FOR-DEMO",
        "expires_at": "2025-03-01T00:00:00Z",
    }


# ── Tool 8: send_notification ────────────────────────────────────

@server.tool(
    name="send_notification",
    description=(
        "Send a notification to a patient or external party. "
        "Marked with maliciousActivityHint because the message content "
        "could contain prompt-injected text. Destination is PUBLIC."
    ),
    annotations=_make_annotations(
        destructive=True,
        trust=TrustAnnotations(
            input_metadata=InputMetadata(
                destination=Destination.PUBLIC,
                sensitivity=SimpleDataClass.NONE,
                outcomes=Outcome.IRREVERSIBLE,
            ),
            malicious_activity_hint=True,
        ),
    ),
)
def send_notification(recipient: str, message: str) -> dict:
    notification = {
        "message_id": _next_msg_id(),
        "recipient": recipient,
        "message": message,
        "status": "sent",
    }
    NOTIFICATIONS.append(notification)
    return {
        "recipient": recipient,
        "status": "sent",
        "message_id": notification["message_id"],
    }


# ===================================================================
# Entry point — stdio transport
# ===================================================================

if __name__ == "__main__":
    server.run(transport="stdio")
