import unittest

from src.scouts.local import run_local_scout


class LocalScoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {
            "schema_version": "0.1",
            "request_id": "spot-local-test-001",
            "requested_at": "2026-09-22T12:00:00+09:00",
            "store": {
                "name": "KT Plaza 명지 에코델타시티점",
                "address": "부산광역시 강서구 명지동",
                "lat": None,
                "lng": None,
            },
            "campaign": {
                "purpose": "신제품 체험 행사 사전 리서치",
                "product": "Galaxy Z Fold8",
                "target_hint": None,
            },
            "research": {
                "reference_date": "2026-09-22",
                "radius_m": 1000,
                "lookback_days": 180,
                "comparison_area": None,
            },
        }

    def test_supported_area_returns_valid_success_result(self) -> None:
        result = run_local_scout(self.request)

        self.assertEqual(result["schema_version"], "0.1")
        self.assertEqual(result["request_id"], "spot-local-test-001")
        self.assertEqual(result["module"], "local")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["insights"]), 3)
        self.assertGreaterEqual(len(result["sources"]), 3)
        self.assertTrue(result["started_at"])
        self.assertTrue(result["finished_at"])
        self.assertEqual(result["errors"], [])

    def test_evidence_preserves_required_local_fields(self) -> None:
        result = run_local_scout(self.request)
        source_ids = {source["source_id"] for source in result["sources"]}

        for source in result["sources"]:
            for field in ("source_url", "published_at", "collected_at", "title"):
                self.assertTrue(source[field])
            self.assertTrue(source["verification"]["verified_at"])
            self.assertTrue(source["verification"]["excerpt"])

        for insight in result["insights"]:
            for field in (
                "evidence",
                "published_at",
                "locality_tags",
                "why_it_matters",
                "change_state",
            ):
                self.assertTrue(insight[field])
            self.assertTrue(set(insight["source_ids"]).issubset(source_ids))

    def test_duplicate_articles_do_not_inflate_change_count(self) -> None:
        result = run_local_scout(self.request)

        tram = next(
            insight for insight in result["insights"] if insight["insight_id"] == "L-002"
        )
        self.assertEqual(len(tram["source_ids"]), 2)
        self.assertEqual(len(result["insights"]), 3)

    def test_unsupported_area_does_not_receive_test_area_evidence(self) -> None:
        self.request["store"] = {
            "name": "KT Plaza 해운대점",
            "address": "부산광역시 해운대구 우동",
        }

        result = run_local_scout(self.request)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["insights"], [])
        self.assertEqual(result["sources"], [])
        self.assertIn("UNSUPPORTED_AREA_WEEK1_POC", result["warnings"][0])

    def test_short_lookback_returns_partial(self) -> None:
        self.request["research"]["lookback_days"] = 30

        result = run_local_scout(self.request)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["insights"], [])
        self.assertTrue(
            any("INSUFFICIENT_RECENT_EVIDENCE" in warning for warning in result["warnings"])
        )
        self.assertIn("확인 가능한 지역 변화 근거가 없다", result["summary"])
        self.assertNotIn("동시에 진행 중", result["summary"])

    def test_single_scheduled_event_summary_mentions_only_that_event(self) -> None:
        self.request["research"]["reference_date"] = "2026-03-29"
        self.request["research"]["lookback_days"] = 0

        result = run_local_scout(self.request)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["insights"]), 1)
        self.assertEqual(result["insights"][0]["change_state"], "scheduled_launch")
        self.assertIn("자율주행 모빌리티 오픈식·시범운행 예정 공지", result["summary"])
        self.assertNotIn("트램", result["summary"])
        self.assertNotIn("특화", result["summary"])

    def test_reference_date_preserves_scheduled_not_launched_stage(self) -> None:
        self.request["research"]["reference_date"] = "2026-03-29"
        self.request["research"]["lookback_days"] = 0

        result = run_local_scout(self.request)

        insight = result["insights"][0]
        self.assertEqual(insight["change_state"], "scheduled_launch")
        self.assertIn("예정", insight["evidence"])
        self.assertTrue(any("실제 운영 개시" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
