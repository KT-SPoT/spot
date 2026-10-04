import unittest
from unittest.mock import patch
from src.scouts.trend import run_trend_scout
from src.scouts.search_runtime import SearchError
from tests.test_local import article

REQUEST = {"request_id": "trend-test", "campaign": {"product": "Galaxy Z Fold8"},
           "research": {"reference_date": "2026-10-01", "lookback_days": 0}}

class TrendTests(unittest.TestCase):
    def test_location_only_search_needs_no_product_and_keeps_nationwide_scope(self):
        request = dict(REQUEST, campaign={'product':None,'purpose':'매장 지역·고객 맥락 리서치'})
        with patch('src.scouts.search_runtime.news',return_value=[article('음식 축제 체험')]), patch('src.scouts.search_runtime.videos',return_value=[]):
            result = run_trend_scout(request)
        self.assertTrue(result['insights'])
        self.assertEqual(result['query_context']['search_queries'], ['팝업','오프라인 체험 행사','2026 10월 축제'])
        self.assertFalse(result['errors'])
        self.assertFalse(any('None' in h['statement'] for c in result['insights'] for h in c['adaptation_hypotheses']))

    def test_video_lookup_can_pause_without_removing_key(self):
        with patch.dict('os.environ', {'SPOT_TREND_VIDEO_MODE': 'off', 'YOUTUBE_API_KEY': 'synthetic-preserved-key'}), \
             patch('src.scouts.search_runtime.news', return_value=[article('게임 팝업 체험')]), \
             patch('src.scouts.search_runtime.videos') as videos:
            result = run_trend_scout(REQUEST)
        videos.assert_not_called()
        self.assertIn('YOUTUBE_LOOKUP_DISABLED', result['warnings'])
        self.assertEqual(result['query_context']['video_mode'], 'off')
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
