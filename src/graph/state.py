"""Shared LangGraph state for SPOT."""

from typing import Any, TypedDict

from src.contracts import ScoutResult, SpotRequest


class SpotState(TypedDict, total=False):
    request: SpotRequest

    quant_result: ScoutResult
    local_result: ScoutResult
    trend_result: ScoutResult

    research_bundle: dict[str, Any]
    critic_result: dict[str, Any]
    research_brief: dict[str, Any]

    retry_targets: list[str]
    retry_count: int
