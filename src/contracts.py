"""Shared lightweight type contracts for SPOT v0.1.

The authoritative field-level contract lives in Notion.
This file keeps only the common shapes needed for module integration.
"""

from typing import Any, Literal, TypedDict


ScoutModule = Literal["quant", "local", "trend"]
ScoutStatus = Literal["success", "partial", "failed"]


class SpotRequest(TypedDict, total=False):
    schema_version: str
    request_id: str
    requested_at: str
    store: dict[str, Any]
    campaign: dict[str, Any]
    research: dict[str, Any]


class ScoutResult(TypedDict, total=False):
    schema_version: str
    request_id: str
    module: ScoutModule
    status: ScoutStatus
    started_at: str | None
    finished_at: str | None
    query_context: dict[str, Any]
    summary: str
    insights: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    warnings: list[Any]
    errors: list[Any]


def mock_scout_result(module: ScoutModule, request_id: str) -> ScoutResult:
    """Return a schema-shaped placeholder without pretending to contain real research."""
    return {
        "schema_version": "0.1",
        "request_id": request_id,
        "module": module,
        "status": "partial",
        "started_at": None,
        "finished_at": None,
        "query_context": {},
        "summary": f"{module} scout placeholder",
        "insights": [],
        "sources": [],
        "warnings": ["MOCK_ONLY_NOT_REAL_DATA"],
        "errors": [],
    }
