"""Actual integrated Scout code, no provider calls or dotenv credentials."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.integration_smoke import run_smoke


class ScoutIntegrationTest(unittest.TestCase):
    def test_actual_scouts_join_with_quant_missing_key(self):
        path = Path(__file__).resolve().parents[1] / "samples/input/myeongji_international.provisional.json"
        request = json.loads(path.read_text(encoding="utf-8"))
        with patch("src.scouts.quant.resolve_address") as geocode, patch("src.scouts.quant.collect_sbiz365_reports") as collect:
            run = run_smoke(request)
        geocode.assert_not_called()
        collect.assert_not_called()
        self.assertTrue(run["graph_completed"])
        self.assertTrue(run["all_contracts_valid"])
        self.assertEqual(run["module_status"], {"quant": "failed", "local": "partial", "trend": "success"})
        bundle = run["state"]["research_bundle"]
        self.assertEqual(bundle["request"], request)
        self.assertEqual(bundle["results"]["quant"]["errors"][0]["code"], "MISSING_KAKAO_REST_API_KEY")
        self.assertEqual({i["insight_id"] for i in bundle["results"]["local"]["insights"]}, {"L-002", "L-003"})
        self.assertEqual(len(bundle["results"]["trend"]["insights"]), 10)
        self.assertEqual(run["state"]["critic_result"]["status"], "manual_review")
        self.assertTrue(run["brief_is_mock"])

    def test_coordinates_skip_geocoding_but_require_sbiz_key(self):
        # Synthetic coordinate input tests routing, not a real store's location.
        request = {"request_id": "coordinate-routing-test", "store": {"lat": 35.0, "lng": 129.0}, "research": {"reference_date": "2026-09-30", "lookback_days": 180}}
        with patch("src.scouts.quant.resolve_address") as geocode, patch("src.scouts.quant.collect_sbiz365_reports") as collect:
            run = run_smoke(request)
        geocode.assert_not_called()
        collect.assert_not_called()
        quant = run["state"]["research_bundle"]["results"]["quant"]
        self.assertEqual(quant["errors"][0]["code"], "MISSING_SBIZ365_CERT_KEY")
        self.assertTrue(run["all_contracts_valid"])

    def test_live_mode_rejects_provisional_area_address(self):
        with patch("src.integration_smoke.build_graph") as graph:
            with self.assertRaisesRegex(ValueError, "실제 조사 주소"):
                run_smoke({"store": {"address": "부산광역시 강서구 명지국제신도시"}}, mode="live")
        graph.assert_not_called()
