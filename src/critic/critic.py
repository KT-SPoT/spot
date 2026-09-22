"""Critic scaffold — owner: 김민석.

The final Critic will combine deterministic rules with LLM-based semantic checks:
- evidence sufficiency
- local specificity
- recency
- differentiation

Retry routing will be added after the three Scout PoCs expose real data.
"""

from typing import Any


def mock_critic(research_bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "request_id": research_bundle.get("request_id", "unknown"),
        "status": "manual_review",
        "checks": {},
        "retry": [],
        "warnings": ["MOCK_CRITIC_NOT_FOR_QUALITY_EVALUATION"],
    }
