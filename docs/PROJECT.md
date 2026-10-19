# SPOT Project

## What SPOT is

SPOT is a **지역 맥락 탐색형 AI Research Agent** for the pre-planning stage of KT Plaza promotion work.

Its job is not to generate a finished event plan immediately. It researches the local area, commercial context, recent local changes, and experience trends, then validates the evidence and produces a **Research Brief**.

User decision (2026-10-04, supersedes the input design of 2026-10-03): research
a specified store/location. Remove candidate-site recommendation, product/model,
free research-purpose and target-hint inputs from the web flow. Product choice,
promotion goal and operating conditions are supplied after the regional brief,
in the planning/handoff stage. Keep one research path. Older product/question
requests remain accepted for compatibility; they are not proof of model-specific
research. The earlier [promotion research design](PROMOTION_RESEARCH_DESIGN.md)
is historical design context, not the current input requirement. Track the shared
interface adjustment in [Issue #44](https://github.com/KT-SPoT/spot/issues/44);
Notion common-document synchronization remains separate.

User clarification (2026-10-02): SBIZ365 agency API observations, including gender,
age and peak day/time, are the quantitative baseline and do not require LLM
re-approval. Preference, attendance and purchase-intent inferences are separate.
Trend researches nationwide, cross-industry offline experiences (for example game
and food popups and regional festivals), guided by the observed population/sales
profiles. Neither store-area nor device/category match is an inclusion condition.
Its key output is the experience mechanism and a research hypothesis for adapting
it to a phone store, rather than a finished promotion plan or a claim of proven appeal.

## Problem

User clarification (2026-10-07): interpret sourced Quant/Local observations before
selecting transferable nationwide experience references. An age word or keyword
overlap is a discovery cue, not a regional insight. Timing distributions and
reported local changes must actually change a planning comparison question.
Keep national references even when they do not supply a regional connection.
Published reports omit collection/quality diagnostic failure sentences; preserve
them in structured diagnostics. This does not certify preference or event impact.

Further user clarification (2026-10-07): useful general findings are a valid
baseline. Regional specificity is an additional point, not a required acceptance
condition. Critic adjusts factual errors, overclaims and incoherent connections;
it does not reject common implications merely for lacking originality. See
[baseline and additional-insight pilot](RESEARCH_SYNTHESIS_PILOT.md) for the local
implementation and its validation/deployment limits.


KT Plaza staff may need to manually check multiple sources such as small-business data, maps, local news, and public web content before planning a promotion.

This creates three problems:
1. research takes time,
2. research depth varies by person,
3. outputs can collapse into generic assumptions such as "new town = family customers."

## Product boundary

- **SPOT**: research → evidence validation → Research Brief
- **흥부장**: Research Brief + operational constraints → execution plan

SPOT should answer:
- What is changing in this area?
- What is distinctive here?
- Why does this matter now?
- What research implications should planners notice?

SPOT should not invent:
- budget,
- staffing,
- event operation details,
- CRM actions,
- claims unsupported by evidence.

## MVP functions

- F-01 Request intake / normalization
- F-02 Quant Scout
- F-03 Local Scout
- F-04 Trend Scout
- F-05 Critic validation / re-search
- F-06 Research Brief
- F-07 흥부장 handoff summary — expansion scope

## MVP non-goals

- sales prediction
- personal customer data
- all-SNS crawling
- fully automatic event planning


## 2026-10-08: 지역 기본 맥락 조사
사용자 승인으로 Local은 뉴스 외에 매장 좌표 기반 Kakao 장소 검색과 공식 정부·지자체 시설 설명을 함께 수집한다. 카테고리/키워드별 가까운 장소를 최대 3개 보존하며 500m 이내와 요청 반경을 구분한다. 장소 검색 개수는 시설 전수나 지배적인 상권 유형, 직선거리는 실제 동선을 뜻하지 않는다. 공식 검색 결과는 원문 본문에서 시설명이 확인될 때만 채택하며 실패는 진단에 남긴다. 최근 변화 뉴스와 지역 배경을 분리한다.

## Next implementation handoff — 2026-10-08

Latest user-approved direction: analyze regional context, patterns and promotional opportunities; narrow the semantic Critic to geographic contamination and scope confusion. This is a planned change, not the currently deployed behavior. Implementation sequence, code locations and acceptance checks are in [ANALYSIS_AGENT_HANDOFF.md](ANALYSIS_AGENT_HANDOFF.md). Preserve data-integrity validation. Notion synchronization is pending.

## 2026-10-08 분석 에이전트 v2 구현 (운영 미반영)

통합 생성은 지역 장소·생활 환경과 소비 패턴을 각각 선택해 지역 해석/홍보 기회를 작성한다. semantic Critic은 지역 혼입·공간 범위·전국 사례의 현지 반응 오인만 교정한다. 참신함·일반성·연령 적합성을 채택 조건으로 사용하지 않는다. 생성 원칙과 출처·수치·모집단·시점 무결성 검사는 유지한다.
구현: src/brief/synthesis.py, connection_synthesis.py, pipeline.py 및 지역 개요/웹/보고서 연결. 새 지역 범위 판정과 내부 생성 스키마는 Research Brief 기존 출력 필드로 매핑한다. Notion 동기화는 대기 중이다.
