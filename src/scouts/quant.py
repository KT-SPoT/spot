"""Quant Scout — owner: 유승우.

TODO(owner):
- Call the small-business OpenAPI.
- Decide usable metrics from the actual API response.
- Transform the result into ScoutResult v0.1.
- Keep API keys in environment variables, never in code.
"""

from src.contracts import ScoutResult, SpotRequest, mock_scout_result


def run_quant_scout(request: SpotRequest) -> ScoutResult:
    # Integration-safe placeholder. Replace internals on feat/quant.
    return mock_scout_result("quant", request.get("request_id", "unknown"))
