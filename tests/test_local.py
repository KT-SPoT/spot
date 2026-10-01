import unittest
from unittest.mock import patch
from src.scouts.local import run_local_scout, area_anchor
from src.scouts.search_runtime import now

REQUEST = {"request_id": "live-test", "store": {"name": "KT플라자 명지국제신도시점"},
           "research": {"reference_date": "2026-10-01", "lookback_days": 180}}

def article(title, url="https://example.org/article"):
    return {"title": title, "description": "개관 예정", "source_url": url, "source_name": "Synthetic",
            "source_type": "news", "published_at": "2026-10-01T10:00:00+09:00", "collected_at": now()}

class LocalTests(unittest.TestCase):
    def setUp(self):
        self.verifier = patch("src.scouts.local.verify_source", return_value={
            "status": "text_corroborated", "article_published_at": "2026-10-01",
            "excerpt": "합성 명지국제신도시 개관 예정 근거", "change_state": "scheduled",
            "evidence_fingerprint": "synthetic", "full_text_verified": True})
        self.verifier.start()
        self.addCleanup(self.verifier.stop)

    def test_filters_wrong_neighborhood_and_duplicates(self):
        rows = [article("에코델타시티 개관"), article("명지국제신도시 개관", "https://example.org/right")]
        with patch("src.scouts.search_runtime.news", return_value=rows):
            result = run_local_scout(REQUEST)
        self.assertEqual(len(result["insights"]), 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["insights"][0]["change_state"], "scheduled")
        self.assertNotEqual(result["sources"][0]["collected_at"][:10], "2026-09-30")

    def test_supports_other_requested_area(self):
        request = dict(REQUEST, store={"address": "서울특별시 강남구 역삼동 123"})
        with patch("src.scouts.search_runtime.news", return_value=[article("역삼동 개관")]):
            result = run_local_scout(request)
        self.assertEqual(result["query_context"]["area_anchor"], "역삼동")
        self.assertEqual(len(result["insights"]), 1)

    def test_missing_location_does_not_guess(self):
        self.assertIsNone(area_anchor({"address": "부산광역시 강서구"}))
        with patch("src.scouts.search_runtime.news") as provider:
            result = run_local_scout(dict(REQUEST, store={"lat": 35, "lng": 129}))
        provider.assert_not_called()
        self.assertEqual(result["status"], "failed")

    def test_identical_report_sentence_merges_source_references(self):
        rows = [article("명지국제신도시 개관", "https://example.org/one"),
                article("명지국제신도시 개관", "https://example.org/two")]
        with patch("src.scouts.search_runtime.news", return_value=rows):
            result = run_local_scout(REQUEST)
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(len(result["insights"]), 1)
        self.assertEqual(len(result["insights"][0]["source_ids"]), 2)

    def test_unreadable_source_does_not_inherit_snippet_stage(self):
        with patch("src.scouts.local.verify_source", return_value={"status": "unavailable", "reason": "SOURCE_HTTP_ERROR"}), patch("src.scouts.search_runtime.news", return_value=[article("명지국제신도시 개관 예정")]):
            result = run_local_scout(REQUEST)
        self.assertEqual(result["insights"][0]["change_state"], "unverified")
        self.assertEqual(result["insights"][0]["evidence_basis"], "search_passage")
