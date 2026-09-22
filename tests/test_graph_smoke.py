"""End-to-end smoke test for the Week-1 mock LangGraph flow."""

import json
import unittest
from pathlib import Path

from src.graph.graph import build_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REQUEST = REPOSITORY_ROOT / "samples/input/spot_request.example.json"


class GraphSmokeTest(unittest.TestCase):
    def test_mock_graph_reaches_research_brief(self) -> None:
        request = json.loads(SAMPLE_REQUEST.read_text(encoding="utf-8"))

        result = build_graph().invoke({"request": request})

        bundle = result["research_bundle"]
        self.assertEqual(bundle["request_id"], request["request_id"])
        self.assertEqual(set(bundle["results"]), {"quant", "local", "trend"})
        self.assertEqual(
            bundle["module_status"],
            {"quant": "partial", "local": "partial", "trend": "partial"},
        )

        for module in ("quant", "local", "trend"):
            scout_result = result[f"{module}_result"]
            self.assertEqual(scout_result["schema_version"], "0.1")
            self.assertEqual(scout_result["request_id"], request["request_id"])
            self.assertEqual(scout_result["module"], module)
            self.assertEqual(scout_result["warnings"], ["MOCK_ONLY_NOT_REAL_DATA"])

        self.assertEqual(result["critic_result"]["status"], "manual_review")
        self.assertEqual(result["research_brief"]["status"], "mock")
        self.assertEqual(
            result["research_brief"]["request_id"], request["request_id"]
        )


if __name__ == "__main__":
    unittest.main()
