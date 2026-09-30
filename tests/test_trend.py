import unittest

from src.scouts.trend import run_trend_scout


def make_request(reference_date: str, lookback_days: int) -> dict:
    return {
        "schema_version": "0.1",
        "request_id": "trend-test",
        "requested_at": "2026-09-30T12:00:00+09:00",
        "store": {
            "name": "KT Plaza 명지 에코델타시티점",
            "address": "부산광역시 강서구 명지동",
        },
        "campaign": {
            "purpose": "신제품 체험 행사 사전 리서치",
            "product": "Galaxy Z Fold8",
        },
        "research": {
            "reference_date": reference_date,
            "lookback_days": lookback_days,
        },
    }


class TrendScoutTest(unittest.TestCase):
    def test_normal_period_returns_success(self) -> None:
        result = run_trend_scout(
            make_request("2026-09-29", 180)
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["query_context"]["selected_case_count"],
            10,
        )
        self.assertEqual(len(result["insights"]), 10)
        self.assertGreaterEqual(len(result["patterns"]), 2)
        self.assertEqual(result["errors"], [])

        collected_at_values = {
            source["collected_at"]
            for source in result["sources"]
        }
        self.assertEqual(
            collected_at_values,
            {"2026-09-30T13:43:21+09:00"},
        )

    def test_short_period_returns_partial(self) -> None:
        result = run_trend_scout(
            make_request("2026-09-29", 3)
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(
            result["query_context"]["selected_case_count"],
            1,
        )
        self.assertIn(
            "INSUFFICIENT_VERIFIED_CASES_WITHIN_LOOKBACK",
            result["warnings"],
        )

    def test_period_with_no_cases_returns_failed(self) -> None:
        result = run_trend_scout(
            make_request("2025-01-01", 30)
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["insights"], [])
        self.assertEqual(result["patterns"], [])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["errors"], [])

    def test_invalid_reference_date_returns_failed(self) -> None:
        result = run_trend_scout(
            make_request("2026-99-99", 180)
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"])
        self.assertEqual(result["query_context"], {})


if __name__ == "__main__":
    unittest.main()
