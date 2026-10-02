# Context-aware Trend integration

## Execution

```text
SpotRequest -> Quant / Local (parallel)
            -> trend_context (join both)
            -> Trend -> Merge -> Rule Critic -> optional semantic shadow -> Research Brief
```

Run the existing graph or research CLI with the same SpotRequest file and
environment configuration described in README. No additional API key is needed.
`python -m unittest discover -s tests -v` verifies the flow without provider calls.

SpotRequest, common ScoutResult and Brief v0.1 fields are preserved. The optional
`run_trend_scout(request, *, context=None)` argument is graph-internal. The graph
state's `trend_context` is not an external request requirement. Standalone Trend
calls continue to work when Quant/Local context is unavailable.

## Context and evidence

Only contract-valid, request-matched, non-failed, non-mock results with sources
contribute. Quant's floating/resident/worker populations and sales gender/age
signals remain separate. The graph reuses the same-run provider archive to pass
available full gender/age shares without raw HTML or credential-bearing URLs;
dominant signals remain usable without that archive. Peak floating/sales day/time
also pass through as observations. Unavailable shares and reference periods are null. Sales
composition is not customer count, and demographics do not establish preferences.
Local contributes at most 10 source-connected corroborated/context-corroborated
signals. The context carries provenance metadata, not credential-bearing URLs or
raw provider archives. Missing context is recorded in warnings.

Trend uses at most three unique queries per provider: game popups, food popups
and regional festivals. Available sales/floating ages refine two queries; one
query stays broad. Gender never assigns an industry or a stereotyped preference.
Search has no store-area or device/category gate. Offline-event wording in news
headlines still prevents related-story snippets from admitting unrelated news.
Product matching remains descriptive metadata, not an inclusion/ranking bonus.
Experience mechanism expressions and at most two literal population/local
overlaps guide ranking. Reference selection keeps available category diversity
within the five-case cap. Event reviews can be useful; unboxing/purchase-link/
lowest-price headlines do not qualify. These are bounded discovery heuristics,
not a claim of exhaustive nationwide coverage or audience demand.

Each candidate separates the source observation, audience research hypothesis
and store/product adaptation questions. For example, a festival stamp mission
can suggest investigating a feature-comparison journey; food sampling can suggest
investigating preference comparison or food photography. These are questions,
not proven device capabilities, event success or a final campaign plan.

SBIZ365 official observations are the quantitative baseline. The semantic input
keeps their fact cards but excludes explicitly marked API observations from LLM
re-approval; inferred preference/intent remains reviewable. Semantic locality
checks are module-aware: Local changes use the declared locality; nationwide
Trend references can be offsite and from other industries.

## PR #14 adoption

Adapted pure helpers from `feat/trend-week2` commit `bcfe647` (PR #14): request-based
product aliases/family matching, brand token boundaries and timestamp exclusion.
Legacy request/product scoring helpers remain available for historical references,
but no longer gate or rank nationwide live discovery. The existing live search
runtime retains explicit date windows, offline controls, deduplication, provider
error handling and per-provider stop after HTTP 429. The upstream 16-query search
expansion is bounded here. Model matching also rejects Fold8 matching Fold80.

The upstream 10-case list is an explicitly historical reference library. Its
recorded verification labels were not rechecked in this run. Up to three entries
within the requested date window are returned in `reference_library`; they never
populate live sources, patterns, success status or the Brief. Empty live results
remain failed even when library entries exist.

## Trend-specific optional output

- `reference_cases`: up to five ranked live search candidates, each with
  `why_relevant`, `limitations`, `context_source_refs`, `event_category`,
  `audience_hypothesis`, `adaptation_hypotheses` and a heuristic score.
- `reference_patterns`: metadata patterns within the selected candidates.
- `reference_library`: past cases, explicitly marked `rechecked_during_run=false`.
- `query_context.upstream_context`: the actual bounded context used.

The Brief's existing `trend_patterns` list carries both pattern cards and
`type=reference_case` cards. Summary counts separate them. Context citations are
resolved by module and source ID; incomplete links remove unsupported context
reasoning. Source counts include cited context URLs and exclude library entries.

## Validation and limits

Tests cover the parallel join, context provenance, missing/failed upstream
results, soft ranking, query bounds, model/brand false positives, timestamp tags,
single-candidate Briefs, broken citations and library-without-live-data failure.
The local verification artifact replays previously collected real Quant/Local
results and saved Trend news records. It performs no new provider requests,
including YouTube, and marks replay provenance explicitly. Search metadata is
not a verified event; the Critic still requires subsequent semantic review.
