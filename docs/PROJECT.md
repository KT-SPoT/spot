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
