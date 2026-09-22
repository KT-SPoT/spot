# n8n

n8n is intentionally kept lightweight.

Current `SPOT - Main Entry` responsibility:

1. Receive POST request through Webhook
2. Normalize basic request fields
3. Validate required fields
4. Call the LangGraph API later through HTTP Request
5. Return the result through Respond to Webhook

The Scout / Critic / retry decision loop belongs to LangGraph, not to n8n.

Current cloud workflow is managed in the team's shared n8n project and is not exported here yet.
