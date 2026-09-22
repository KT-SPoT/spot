"""Local Scout — owner: 김태훈.

TODO(owner):
- Search recent local changes from reliable public/news sources.
- Preserve source URL and publication date.
- Define locality tags and duplicate handling.
- Transform the result into ScoutResult v0.1.
"""

from src.contracts import ScoutResult, SpotRequest, mock_scout_result


def run_local_scout(request: SpotRequest) -> ScoutResult:
    # Integration-safe placeholder. Replace internals on feat/local.
    return mock_scout_result("local", request.get("request_id", "unknown"))
