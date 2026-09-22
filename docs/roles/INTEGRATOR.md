# Integrator / Critic / Research Brief — 김민석

## Mission
Make the three Scouts behave as one coherent Research Agent.

## Main branch
`feat/critic`

## Owned areas
- `src/contracts.py`
- `src/graph/`
- `src/critic/`
- `src/brief/`
- n8n ↔ LangGraph integration
- shared-contract synchronization

## Week 1 checklist
- [x] n8n Main Entry
- [x] LangGraph skeleton
- [x] Scout placeholders
- [ ] run local mock E2E smoke test
- [ ] validate real Scout samples against the contract
- [ ] replace placeholders incrementally
- [ ] implement rule-based Critic v0.1
- [ ] draft retry routing
- [ ] define retry limit / manual review behavior

## Current GitHub Issue
#4 — LangGraph mock E2E / Critic prep

## Review responsibility
For each Scout PR, verify:
- input contract,
- output contract,
- real vs mock status,
- evidence/source metadata,
- failure behavior,
- shared-contract impact.
