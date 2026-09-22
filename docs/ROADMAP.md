# SPOT Roadmap

## Current state — 2026-09-22

### Completed
- n8n shared project created
- `SPOT - Main Entry` Webhook created
- input normalization completed
- required-field validation completed
- success / failure mock responses tested
- GitHub repository initialized
- common LangGraph skeleton created
- Quant / Local / Trend placeholder functions created
- common contract scaffold created
- feature branches created
- GitHub Issues #1–#4 created

### In progress now
- Quant: Small-business OpenAPI PoC
- Local: local-change evidence PoC
- Trend: YouTube / public-web case PoC
- Integrator: LangGraph mock E2E smoke test

### Do not prioritize yet
- n8n AI Agent node
- implementing Scout loops inside n8n
- sophisticated LLM Critic prompting
- 흥부장 integration
- UI work

## Week 1 — prove integration is possible

Goal:
- every Scout can return `ScoutResult v0.1`,
- LangGraph can merge results and produce a mock Brief.

Deliverables:
- Quant real API result
- Local 3+ real local-change evidence items
- Trend 5+ real cases and pattern draft
- Integrator mock E2E run

## Week 2 — improve Scout quality

- finalize Quant metrics
- finalize Local query/source policy
- finalize Trend taxonomy
- align evidence / date / source fields
- define Critic MVP thresholds

## Week 3 — Agent loop and external connection

- integrate all three real Scouts
- implement rule-based + semantic Critic
- implement retry routing and stop conditions
- expose LangGraph through an API
- connect n8n HTTP Request to LangGraph

## Week 4 — test and present

- test 2–3 contrasting commercial areas
- compare baseline research vs SPOT
- finalize Research Brief format
- prepare demo and presentation
