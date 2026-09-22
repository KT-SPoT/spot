# SPOT API Contract

The source of truth is the Notion page **00. SPOT 공통 Input/Output JSON Schema**.

## Shared types

- Input: `SpotRequest v0.1`
- Scout output: `ScoutResult v0.1`
- Merge: `ResearchBundle v0.1`
- Critic: `CriticResult v0.1`
- Final: `ResearchBrief v0.1`

## Rule

Each Scout may use a different API, search strategy, or internal implementation, but it must accept the shared request shape and return the shared ScoutResult shape.

Missing optional values should be represented as `null` or empty arrays rather than deleting fields.

## Secrets

Do not commit API keys or credentials. Use environment variables locally and n8n Credentials where applicable.
