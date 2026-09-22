"""Research Brief scaffold — owner: 김민석."""

from typing import Any


def mock_brief(request_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "request_id": request_id,
        "status": "mock",
        "overview": {
            "area_summary": "SPOT mock Research Brief",
            "primary_customer_signal": None,
        },
        "local_changes": [],
        "unique_local_signals": [],
        "trend_patterns": [],
        "why_here_now": "Mock only. Real Scout evidence is not connected yet.",
        "research_implications": [],
        "needs_manual_check": ["Connect real Scout outputs before using this result."],
        "source_count": 0,
    }
