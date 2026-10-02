import unittest
from unittest.mock import patch
from src.scouts.trend import run_trend_scout
from src.scouts.search_runtime import SearchError
from tests.test_local import article

REQUEST = {"request_id": "trend-test", "campaign": {"product": "Galaxy Z Fold8"},
           "research": {"reference_date": "2026-10-01", "lookback_days": 0}}

class TrendTests(unittest.TestCase):
    def test_relevance_and_pattern_candidates(self):
        rows = [article("갤럭시 Z 폴드8 팝업 체험", "https://example.org/1"),
                article("스마트폰 팝업 체험", "https://example.org/2"),
                article("화장품 팝업 체험", "https://example.org/3"),
                article("갤럭시 Z 폴드8 온라인 리뷰", "https://example.org/4")]
        with patch("src.scouts.search_runtime.news", return_value=rows), patch("src.scouts.search_runtime.videos", return_value=rows):
            result = run_trend_scout(REQUEST)
        self.assertEqual(len(result["insights"]), 3)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["patterns"][0]["verification_status"], "candidate")
        self.assertEqual(result["query_context"]["lookback_days"], 0)
        self.assertTrue(any(c['request_relevance'] == 'same_product' for c in result['insights']))
        self.assertIsNone(result["insights"][0]["location"])

    def test_provider_failure_still_collects_other_provider(self):
        with patch("src.scouts.search_runtime.news", side_effect=SearchError("PROVIDER_HTTP_ERROR", 403)), patch("src.scouts.search_runtime.videos", return_value=[article("스마트폰 팝업 체험")]):
            result = run_trend_scout(REQUEST)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["errors"][0]["http_status"], 403)

    def test_no_fixed_pool_fallback(self):
        with patch("src.scouts.search_runtime.news", side_effect=SearchError("MISSING_NAVER_CREDENTIALS")), patch("src.scouts.search_runtime.videos", side_effect=SearchError("MISSING_YOUTUBE_API_KEY")):
            result = run_trend_scout(REQUEST)
        self.assertEqual(result["insights"], [])
        self.assertEqual(result["status"], "failed")

    def test_related_story_text_does_not_make_unrelated_headline_relevant(self):
        row = article("라면 신제품 출시")
        row["description"] = "관련 기사: 갤럭시 Z 폴드8 팝업 체험"
        with patch("src.scouts.search_runtime.news", return_value=[row]), patch("src.scouts.search_runtime.videos", return_value=[]):
            self.assertEqual(run_trend_scout(REQUEST)["insights"], [])

    def test_news_capacity_leaves_room_for_video_sources(self):
        rows = [article("스마트폰 팝업 체험", f"https://example.org/{i}") for i in range(12)]
        video = dict(article("스마트폰 팝업 체험", "https://www.youtube.com/watch?v=abcdefghijk"), source_type="youtube")
        with patch("src.scouts.search_runtime.news", return_value=rows), patch("src.scouts.search_runtime.videos", return_value=[video]):
            result = run_trend_scout(REQUEST)
        self.assertEqual(len(result["sources"]), 11)
        self.assertEqual(sum(s["source_type"] == "youtube" for s in result["sources"]), 1)
