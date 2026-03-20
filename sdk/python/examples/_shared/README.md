# Shared: Healthcare Clinic MCP Server

Stdio-based MCP server with 8 SEP-1913 annotated tools covering a range of sensitivity levels:

| Tool | Sensitivity | Key Annotations |
|------|-------------|-----------------|
| `health_check` | none | read-only |
| `patient_lookup` | regulated(HIPAA) | PHI, internal source |
| `search_patients` | regulated(HIPAA) | PHI, internal source |
| `update_patient_record` | regulated(HIPAA) | destructive, consequential |
| `staff_directory` | PII | internal source |
| `process_insurance_claim` | financial | consequential |
| `rotate_api_key` | credentials | system source |
| `send_notification` | none | public destination, malicious-activity hint |

## Usage

```bash
cd sdk/python
PYTHONPATH=src python examples/_shared/mcp_server.py
```

This server is started automatically by the other examples via stdio transport.
