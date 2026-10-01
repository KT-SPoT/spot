# n8n

Importable inactive adapter: [spot-research-api.json](spot-research-api.json).
Setup, API execution, credentials and submit/status usage:
[N8N_API_SETUP.md](../../docs/N8N_API_SETUP.md).
The exported template has no credential values or IDs and does not replace the team's cloud workflow.

n8n is intentionally kept lightweight.

Current `SPOT - Main Entry` responsibility:

1. Receive POST request through Webhook
2. Normalize basic request fields
3. Validate required fields
4. Call the LangGraph API later through HTTP Request
5. Return the result through Respond to Webhook

The Scout / Critic / retry decision loop belongs to LangGraph, not to n8n.

Current cloud workflow is managed in the team's shared n8n project and is not exported here yet.
