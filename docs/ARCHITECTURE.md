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
    ├─ Quant Scout ─┐
    └─ Local Scout ─┴─ Internal context summary
                            ↓
                        Trend Scout
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

The current graph runs Quant and Local in parallel, joins both results, then
passes a bounded context to Trend. SpotRequest v0.1 is unchanged. Trend still
supports `run_trend_scout(request)`; its optional keyword `context` is internal
to the graph. See [context-aware Trend](CONTEXT_AWARE_TREND.md).
The Critic now uses real deterministic checks and at most one selected-module
retry for explicitly transient provider failures. Semantic/factual approval
remains manual. See [current retry policy](CRITIC_RETRY.md); broader quality retries
below remain the target flow.

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
- Local: is the claimed change specific to the declared area?
- Local: does this differentiate the area?
- are the three Scout outputs meaningfully connected?
- Trend: is the nationwide experience mechanism connected to this store's audience
  through an explicit adaptation hypothesis, without inventing preference or impact?

Official SBIZ365 observations are an accepted quantitative baseline, not LLM
approval targets. Coordinates, source links, parser consistency and unknown
reference periods remain deterministic data-handling concerns. Trend cases may be
outside the store area and product category; locality restrictions apply to Local
claims, not to nationwide Trend references.

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
