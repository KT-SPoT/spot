# SPOT Architecture

## High-level flow

```text
External Request
    ↓
n8n Main Entry
- Webhook
- basic input normalization
- required-field validation
    ↓
LangGraph
    ├─ Quant Scout
    ├─ Local Scout
    └─ Trend Scout
          ↓
       Merge
          ↓
       Critic
          ↓
  PASS / RETRY / MANUAL REVIEW
          ↓
   Research Brief
          ↓
n8n Response
```

## Why n8n + LangGraph

### n8n
n8n is intentionally kept lightweight.

Responsibilities:
- receive external requests,
- validate basic required fields,
- call the LangGraph API,
- return the final result,
- later connect external delivery systems if needed.

### LangGraph
LangGraph owns the Agent execution flow.

Responsibilities:
- shared state,
- Scout execution,
- merge,
- Critic,
- retry routing,
- retry limit,
- final Brief generation.

## Scout boundary

Each Scout is an independent module.

```text
SpotRequest v0.1
    ↓
run_*_scout(request)
    ↓
ScoutResult v0.1
```

Scout owners can choose their own APIs, libraries, and internal logic as long as the shared contract is preserved.

## Critic layers

### Rule-based checks
Use code for deterministic checks:
- source count,
- source/date presence,
- recent evidence,
- result count,
- comparator presence,
- retry count.

### LLM semantic checks
Use an LLM for meaning-dependent checks:
- is this generic or genuinely local?
- does this differentiate the area?
- are the three Scout outputs meaningfully connected?
- is the rationale specific enough to this location?

## Target retry flow

```text
Critic PASS
  → Brief

Quant evidence insufficient
  → Quant retry

Local specificity insufficient
  → Local retry

Trend / recency insufficient
  → Trend retry

Retry limit exceeded
  → manual_review
```
