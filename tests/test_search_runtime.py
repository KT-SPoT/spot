import os
import unittest
from datetime import date
from urllib.error import HTTPError
from unittest.mock import patch
from src.scouts import search_runtime as search

class RuntimeTests(unittest.TestCase):
    def test_rate_limit_skips_next_query_in_same_run(self):
        output = search.result({}, "trend")
        with patch.object(search, "videos", side_effect=search.SearchError("PROVIDER_HTTP_ERROR", 429)) as provider:
            search.collect(output, provider, "one", date(2026,1,1), date(2026,10,1))
            search.collect(output, provider, "two", date(2026,1,1), date(2026,10,1))
        self.assertEqual(provider.call_count, 1)

    def test_zero_and_invalid_window(self):
        self.assertEqual(search.window({"research": {"reference_date": "2026-10-01", "lookback_days": 0}}), (date(2026,10,1), date(2026,10,1), 0))
        for days in (-1, True, "180"):
            with self.assertRaises(ValueError):
                search.window({"research": {"lookback_days": days}})

    def test_offline_prevents_dotenv_and_network(self):
        with patch.dict(os.environ, {"SPOT_SCOUT_MODE": "offline"}), patch.object(search, "load_dotenv") as dotenv, patch.object(search, "urlopen") as network:
            with self.assertRaises(search.SearchError):
                search.news("지역", date(2026,1,1), date(2026,10,1))
        dotenv.assert_not_called()
        network.assert_not_called()

    def test_http_error_does_not_expose_key_or_body(self):
        with patch.object(search, "urlopen", side_effect=HTTPError("https://example.org/?key=SECRET", 403, "SECRET", {}, None)):
            with self.assertRaises(search.SearchError) as caught:
                search.get_json("https://example.org/", {"key": "SECRET"})
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(caught.exception.status, 403)

    def test_news_date_filter_and_hub_auth_fallback(self):
        row = {"title": "<b>지역</b>", "originallink": "https://example.org/article", "pubDate": "Thu, 01 Oct 2026 00:00:00 +0900"}
        with patch.object(search, "credentials"), patch.dict(os.environ, {"NAVER_CLIENT_ID": "synthetic", "NAVER_CLIENT_SECRET": "synthetic", "NAVER_SEARCH_PROVIDER": "auto"}), patch.object(search, "get_json", side_effect=[search.SearchError("PROVIDER_HTTP_ERROR",401), {"items": [row, dict(row, pubDate="Fri, 02 Oct 2026 00:00:00 +0900"), dict(row, pubDate="invalid")]}]) as get:
            result = search.news("지역", date(2026,10,1), date(2026,10,1))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["title"], "지역")
        self.assertIn("naverapihub", get.call_args.args[0])

    def test_video_window_and_full_metadata(self):
        data = {"items": [{"id": {"videoId": "abcdefghijk"}}]}
        details = {"items": [{"id": "abcdefghijk", "snippet": {"title": "체험존", "description": "full", "publishedAt": "2026-09-30T15:00:00Z"}}]}
        with patch.object(search, "credentials"), patch.dict(os.environ, {"YOUTUBE_API_KEY": "synthetic"}), patch.object(search, "get_json", side_effect=[data, details]) as get:
            result = search.videos("test", date(2026,10,1), date(2026,10,1))
        self.assertEqual(get.call_args_list[0].args[1]["publishedAfter"], "2026-09-30T15:00:00Z")
        self.assertEqual(result[0]["description"], "full")
