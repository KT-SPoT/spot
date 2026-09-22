# SPOT Project

## What SPOT is

SPOT is a **지역 맥락 탐색형 AI Research Agent** for the pre-planning stage of KT Plaza promotion work.

Its job is not to generate a finished event plan immediately. It researches the local area, commercial context, recent local changes, and experience trends, then validates the evidence and produces a **Research Brief**.

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
