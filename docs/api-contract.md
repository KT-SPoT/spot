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
- `claim_kind=public_api_observation` on API-derived observation insights; inferred
  preferences/intent must not use this marker. With SBIZ365 provenance, observations
  are supplied as the quantitative baseline instead of LLM re-approval claims.

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
- Optional case-level `event_category`, `audience_hypothesis` and
  `adaptation_hypotheses` (`kind=research_question`, `mechanism`, `statement`). These
  are Trend-specific extensions; existing common v0.1 fields stay unchanged.
- Collection scope is nationwide and cross-industry. A case need not match the
  store's area, device or product category. Audience response is a hypothesis unless
  separately evidenced; adaptation questions identify how the mechanism could be
  used in a phone store.
- `reference_cases[].related_case_ids` may link selected related-coverage cases
  within the same conservative group; one group occupies one reference slot.
- `audience_contexts` may carry survey/participation-intent evidence separately
  from event cases. Such context is not counted as a repeated experience pattern.
- Optional `case_detail` records bounded original-article wording checks, source
  IDs, publication date (nullable), mechanisms and reported response expressions.
  `status=text_corroborated` does not verify an event or audience preference.
- Optional `audience_fit` carries `kind=research_hypothesis`, population kind,
  observed profile, Quant context source refs, Trend mechanism source IDs,
  mechanism basis, rationale and next check. `fit_status=hypothesis_not_proven_preference`
  explicitly separates cohort composition from appeal. See `TREND_EVIDENCE_FIT.md`.
- [Issue #34](https://github.com/KT-SPoT/spot/issues/34): `audience_fit` may add
  `question_basis` entries (`axis`, `rule`, `observation`, `question`,
  `context_source_refs`). These describe evidence-conditioned comparison design
  for complete distributions, population kind, peak timing and corroborated Local
  context. They do not assert age/gender preference, joint cohorts or efficacy.
  `why_relevant` distinguishes discovery selection from subsequent adaptation
  reasoning; adaptation hypotheses use article mechanisms when available.
  No required v0.1 field or status changes. See `TREND_AUDIENCE_ADAPTATION.md`.

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

### Optional Quant distribution cards

Tracked for Integrator review in [Issue #38](https://github.com/KT-SPoT/spot/issues/38).
The implementation may add `type=quant_distribution` cards to the existing
`unique_local_signals` list. Each preserves `module=quant`, `population_kind`
(`floating_population` or `sales`), `distribution_kind` (`gender`, `age`, `day`,
`time`), `shares` of recognized keys with numeric `share_pct` (and optional
observed `count`), nullable table-specific `reference_period`, `scope`, `sources`
and `evidence_basis`. Sales cards contain amount shares, not transaction shares.
The data is extracted from the validated same-run Quant archive; no fresh call is
made to populate a graph. Population demographic cards without this `type` or
`distribution_kind` remain supported. Required v0.1 fields are unchanged.
See [Quant charts](QUANT_CHARTS.md). This repository proposal does not assert that
the common Notion documentation has already been synchronized.

## Missing values

- unknown value: `null`
- investigated but no result: `[]`
- do not silently delete common fields

## Secrets

Never commit API keys or credentials.
Use local environment variables and n8n Credentials where applicable.

## Optional research job progress (web transport)

Tracked in [Issue #32](https://github.com/KT-SPoT/spot/issues/32). The job polling
response may include `progress: {stages, updated_at}`. This is transport metadata,
not a new required field in SpotRequest, ScoutResult, or ResearchBrief.
`stages` maps graph nodes (`quant`, `local`, `trend`, `merge`, `critic`, `retry`,
`semantic`, `brief`) to actual execution states (`running`, `success`, `partial`,
`failed`, `completed`). Consumers must tolerate missing stages/metadata. A completed
node means execution ended, not that facts or recommendations were certified.
See [web experience](web-experience.md) for display and compatibility rules.
# 선택적인 탐색 메타데이터 (2026-10-03, Issue #42)

Trend Scout v0.1의 기존 자유 형식 `query_context`에 `search_plan` 배열을 추가한다.
각 항목은 `role`(broad/request/timing), `query`, `reason`이다. 기존 필수 필드·상태는 바뀌지 않는다.
연구 HTTP 완료 결과에는 선택 필드 `trend_discovery`로 `search_plan`, `reference_date`,
`lookback_start`를 전달한다. 과거/오프라인 결과에서는 없거나 null일 수 있다.
Research Brief v0.1 필수 스키마에는 추가하지 않는다. 후속 공통 Notion 문서 동기화는 Integrator가 담당한다.
