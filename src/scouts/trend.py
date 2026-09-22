"""Trend Scout — owner: 김건희.

TODO(owner):
- Validate YouTube Data API / public web sources.
- Collect experiential marketing examples.
- Extract reusable experience-pattern taxonomy.
- Transform the result into ScoutResult v0.1.
"""

from src.contracts import ScoutResult, SpotRequest, mock_scout_result


def run_trend_scout(request: SpotRequest) -> ScoutResult:
    # Integration-safe placeholder. Replace internals on feat/trend.
    return mock_scout_result("trend", request.get("request_id", "unknown"))
