# Research targeting — 2026-10-07

User decision: use sales amount shares before population shares for the planning
target candidate. These are area-level commercial observations, not a count of
the KT store's customers or evidence of product preference. Gender and age are
separate distributions. Keep missing values missing; do not infer joint cohorts.

- Compact handoff: prefer sales shares for age, gender, weekday and time. When
  unavailable, use separately labelled floating/resident/worker observations.
- Promotional items: retain an observed participation mechanism only when the
  case's observation explicitly mentions the selected age, has sources, and is
  not marked generic/needs-context/overstated by an available Critic review. Do
  not turn arbitrary goods into sticker/card recommendations or infer appeal.
  Without an appropriate connection the field remains blank. Product and staff
  fields remain blank. Event age wording alone does not prove audience preference.
- Trend: keep one broad nationwide search and one calendar search. Add the
  observed primary age to the remaining search without assigning stereotyped
  interests or filtering out all other cohorts. Sales takes precedence over
  population. Retain the three-search cap per provider. Video searches use event
  names discovered in news (prefer quoted names, deduplicate matching names) and
  reserve one query for the primary-age popup search. If none are available use
  the discovery queries.
  Reject video results lacking any distinctive event-query term when available.
  Require an offline-event cue in video headlines; description-only related
  links do not qualify a video. This can omit loosely titled vlog references.
  This is lexical association, not a verification of video content.
- Local: for road-only addresses also search the requested city and district.
  Require both city and district in candidate metadata; classify these results
  as surrounding administrative context, never a confirmed store-area change.
  Empty matching results are distinct from provider errors and do not prove that
  no changes occurred. The article-check limit remains 15.

Public SpotRequest and ScoutResult v0.1 boundaries are unchanged. Existing saved
briefs are not silently rewritten; new Scout searches need a new request. The
internal frozen-snapshot evaluator requires caches for every age-dependent query
and continues to forbid live fallback. Tests use synthetic observations and
provider responses; real search quality still depends on available coverage.

Overview follow-up: the overview metric, headline, tags, first insight and age
chart now prefer sales amount shares. Population fallback is labelled explicitly;
floating populations are not called store visitors. Backend primary-customer
summary also prefers sales age shares (or a separately reported sales age when
shares are unavailable). Existing saved briefs can render the corrected client
selection from their existing cards; the saved JSON is not rewritten.

Deployment: Seoul API and web use `spot-app:20261007-sales-overview`. Related Python
regressions: 128 passed; browser-module tests for planning, workspace and media
passed. Production-image checks cover the asset route, attachment download, PDF,
sales-first selection, blank unsupported promotional hints, district queries and
description-only video ad exclusion. No GPT calls were made for these checks.

Bounded live checks: the NamBusan address returned 13 Local source candidates
(12 district-context candidates and one unclassified, no direct-change label).
Trend searches using the saved October 4 Gwanghwamun Quant age observations
queried `20대 오프라인 체험 행사`; shortened event-name and `20대 팝업` video
queries returned six video candidates before the additional headline filter.
One price-ad headline exposed description-only matching; a regression and the
final filter exclude that behavior. These checks are not a newly completed
three-Scout/GPT brief, and the archived Quant observations were not refreshed.

Trend reading follow-up (October 7): context-linked case representatives reserve
up to two shortlist slots before category coverage. The client orders saved cases
using Critic verdicts, literal sales-age mentions in event observations and
available context scores. Shared national cases can still be relevant to multiple
stores; selection is not forced to differ without evidence. New Scout shortlist
selection requires a new research request.

The case-to-store section now separates local observations, observed case actions
and planning questions into readable rows. Selection reasons and context-source
links are visible by default. The Instagram visual-reference section was removed
from this view; existing backend configuration is retained.

Related Python tests: 65 passed; the trend-board Node tests passed. The deployment
image is `spot-app:20261007-trend-reading`. Download and PDF checks use mocks and
do not start fresh Scout or GPT calls.

Regional interpretation revision (October 7, supersedes the age-word sorting
above): Brief implications now start from sourced sales age, day/time shares and
reported Local changes. Timing/local lenses guide nationwide search queries.
Age-word or gender-word overlap does not increase regional fit scores. A concrete
reported action plus a sourced timing/local question is required for case-to-store
connections; an incoherent or overstated connection keeps the case as a national reference.
Even a positive model verdict cannot promote a case without such a connection.

Web, Markdown and PDF distinguish observations, interpretations and planning
questions. Report copy omits collection failure sentences and Critic diagnostic
reasons, while structured diagnostics retain them. Original citations, reference
periods and population distinctions remain intact. No preference/effect approval
is implied. Empty editorial sections do not create blank PDF pages.

The video library has a separate collection path and remains visible independently
of article-case selection. Lookup status is shown outside report prose. A bounded
live check used the saved October 4 Quant observations for Dongnae and Gwanghwamun:
the former queried weekend experiences and the latter weekday experiences; both
returned 10 news candidates with different shortlists. Quant/GPT were not refreshed.
YouTube returned no videos; a single direct diagnostic returned HTTP 429 with
`rateLimitExceeded`. This is a provider request limit, not an empty research verdict.

Related Python regressions: 100 passed; trend-board Node tests passed. Production
image: `spot-app:20261007-regional-insights-v3`. Deployment checks preserve download,
PDF, sales-first interpretation and credential-safe provider handling.

Later clarification (October 7): generic is a baseline contribution, not a reason
to delete a coherent, appropriately scoped planning connection. Differentiation
is optional. This local policy update supersedes the non-useful-verdict rule
above; it has not yet been deployed. The separate stored-Brief synthesis pilot
and observed limits are documented in [RESEARCH_SYNTHESIS_PILOT.md](RESEARCH_SYNTHESIS_PILOT.md).
