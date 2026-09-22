# SPOT AI / Agent Collaboration Guide

This repository is the primary workspace for implementation and AI-assisted development.

## Operating model

- **GitHub**: code, technical implementation, Issues, branches, Pull Requests, AI coding work
- **Notion**: project definition, common decisions, roadmap, shared schema documentation, human-readable role pages
- **Notion MCP**: maintained by the Integrator/team lead for common documentation
- Team Scout AIs should not depend on Notion MCP access. Work from this repository and the implementation contract mirrored here.

## Team ownership

| Role | Owner | Branch | Main file |
| --- | --- | --- | --- |
| Quant Scout | 유승우 | `feat/quant` | `src/scouts/quant.py` |
| Local Scout | 김태훈 | `feat/local` | `src/scouts/local.py` |
| Trend Scout | 김건희 | `feat/trend` | `src/scouts/trend.py` |
| Integrator / Critic / Brief | 김민석 | `feat/critic` | `src/graph/`, `src/critic/`, `src/brief/` |

## What Scout AIs should do

1. Read this file, `README.md`, and `docs/api-contract.md`.
2. Checkout the assigned feature branch.
3. Modify only the assigned Scout area unless a cross-cutting change is explicitly requested.
4. Keep the public function boundary:
   - `SpotRequest v0.1 -> ScoutResult v0.1`
5. Use real evidence/source metadata for non-mock results.
6. Add or update tests/samples when practical.
7. Commit changes and open a Pull Request with:
   - input used
   - output example
   - real vs mock status
   - failure cases / known limitations

## What Scout AIs should not do

- Do not redesign LangGraph orchestration.
- Do not edit another Scout's implementation.
- Do not silently change shared JSON fields.
- Do not put API keys, tokens, n8n credentials, or passwords in Git.
- Do not rely on direct Notion edits for implementation work.

If a shared contract change is needed, open a GitHub Issue describing:
- current problem
- proposed change
- reason/evidence
- affected modules
- urgency

The Integrator reviews the proposal, updates the common Notion docs if accepted, then syncs the implementation contract in GitHub.

## Integrator responsibilities

The Integrator owns:
- shared contracts
- LangGraph state and routing
- merge behavior
- Critic
- Research Brief
- n8n <-> LangGraph integration
- synchronization between common Notion docs and the GitHub implementation contract

## Source-of-truth rule

- Product intent / project decisions / common governance: **Notion**
- Executable code / current implementation behavior: **GitHub**
- Shared interface: documented in Notion and mirrored in `docs/api-contract.md`

If the two disagree, do not guess. Open an Issue and ask the Integrator to reconcile them.
