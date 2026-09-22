# SPOT API Contract

This file is the **implementation mirror** of the common schema managed in Notion.

- Product/common-document source of truth: Notion — **00. SPOT 공통 Input/Output JSON Schema**
- Implementation source of truth: this repository
- If the two disagree, open a GitHub Issue instead of silently changing fields.

## SpotRequest v0.1

```json
{
  "schema_version": "0.1",
  "request_id": "spot-example-001",
  "requested_at": "2026-09-22T12:00:00+09:00",
  "store": {
    "name": "KT Plaza 테스트점",
    "address": "부산광역시 강서구 ...",
    "lat": null,
    "lng": null
  },
  "campaign": {
    "purpose": "신제품 체험 행사 사전 리서치",
    "product": "Galaxy Z Fold8",
    "target_hint": null
  },
  "research": {
    "reference_date": "2026-09-22",
    "radius_m": 1000,
    "lookback_days": 180,
    "comparison_area": null
  }
}
```

## ScoutResult v0.1 — common envelope

All Scouts must return these common fields. A Scout may add module-specific fields such as `metrics` or `patterns`.

```json
{
  "schema_version": "0.1",
  "request_id": "spot-example-001",
  "module": "quant",
  "status": "success",
  "started_at": "2026-09-22T12:00:01+09:00",
  "finished_at": "2026-09-22T12:00:05+09:00",
  "query_context": {},
  "summary": "핵심 결과 요약",
  "insights": [],
  "sources": [],
  "warnings": [],
  "errors": []
}
```

### Allowed status values

- `success`
- `partial`
- `failed`

## Source metadata

Evidence-bearing results should preserve, where available:

```json
{
  "source_id": "S-L-001",
  "source_name": "source name",
  "source_type": "government",
  "source_url": "https://...",
  "published_at": "2026-09-01",
  "collected_at": "2026-09-22T12:00:00+09:00"
}
```

## Module-specific extensions

### Quant

May add:
- `metrics`
- category/store/competition counts
- metric references inside insights

### Local

Insights should preserve:
- concrete evidence
- source references
- publication date
- locality tag
- why the change matters

### Trend

May add:
- `patterns`
- evidence counts
- example source IDs
- pattern taxonomy tags

## ResearchBundle v0.1

```json
{
  "schema_version": "0.1",
  "request_id": "spot-example-001",
  "request": {},
  "results": {
    "quant": {},
    "local": {},
    "trend": {}
  },
  "module_status": {
    "quant": "success",
    "local": "success",
    "trend": "partial"
  }
}
```

A `partial` Scout does not automatically stop the whole flow. The Critic decides what to do next.

## CriticResult v0.1

Critic checks:
- evidence sufficiency
- local specificity
- recency
- differentiation

Status:
- `pass`
- `retry_required`
- `manual_review`
- `failed`

Retry instructions must identify the target module and reason.

## ResearchBrief v0.1

The Brief is a research output, not a finished event plan.

It should contain:
- area summary
- primary customer signal
- recent local changes
- unique local signals
- trend patterns
- why here / why now
- research implications
- manual-check items
- source count

## Missing values

- unknown value: `null`
- investigated but no result: `[]`
- do not silently delete common fields

## Secrets

Never commit API keys or credentials.
Use local environment variables and n8n Credentials where applicable.
