import unittest
from unittest.mock import patch
from src.scouts.trend import run_trend_scout
from src.scouts.search_runtime import SearchError
from tests.test_local import article

REQUEST = {"request_id": "trend-test", "campaign": {"product": "Galaxy Z Fold8"},
           "research": {"reference_date": "2026-10-01", "lookback_days": 0}}

class TrendTests(unittest.TestCase):
    def test_context_candidates_are_not_crowded_out_by_category_coverage(self):
        from src.scouts.trend import diversified_references
        cases=[{'case_id':str(i),'event_name':name,'event_category':category,'context_match_score':score,
                'reference_priority_score':score+3} for i,(name,category,score) in enumerate([
            ('공통 게임 행사','game',0),('공통 음식 행사','food',0),('고객 연결 게임 A','game',4),('고객 연결 게임 B','game',3),('공통 문화 행사','culture',0)])]
        chosen=diversified_references(cases,limit=3)
        self.assertEqual([c['event_name'] for c in chosen[:2]],['고객 연결 게임 A','고객 연결 게임 B'])
        self.assertEqual(len(chosen),3)

    def test_sales_age_changes_search_and_video_queries_follow_events(self):
        from src.scouts.trend import build_queries
        context={'request_id':REQUEST['request_id'],'population_signals':[
            {'population_kind':'floating_population','dominant_age':'60_plus','source_ids':['flow']},
            {'population_kind':'sales','dominant_age':'20s','source_ids':['sales']}]}
        queries=build_queries(REQUEST,context)
        self.assertIn('20대',queries[1]);self.assertNotIn('60대',queries[1])
        context['population_signals'][1]['dominant_age']='40s'
        self.assertIn('40대',build_queries(REQUEST,context)[1])
        rows=[article('별빛 브랜드 40대 팝업 직접 체험','https://example.org/event')]
        unrelated=dict(article('홍대 다른브랜드 팝업 체험','https://www.youtube.com/watch?v=abcdefghijk'),source_type='youtube')
        related=dict(article('별빛 브랜드 팝업 직접 체험','https://www.youtube.com/watch?v=klmnopqrstu'),source_type='youtube')
        with patch('src.scouts.search_runtime.news',return_value=rows),patch('src.scouts.search_runtime.videos',side_effect=lambda q,*_: [unrelated,related] if '별빛' in q else []) as videos:
            result=run_trend_scout(REQUEST,context=context)
        self.assertEqual(videos.call_count,2)
        self.assertIn('별빛 브랜드',videos.call_args_list[0].args[0])
        self.assertEqual(videos.call_args_list[1].args[0],'40대 팝업')
        self.assertEqual([s['source_url'] for s in result['sources'] if s['source_type']=='youtube'],[related['source_url']])

    def test_quoted_event_names_dedupe_headlines_and_keep_audience_lane(self):
        rows=[article("이마트 현대카드와 '와인그랩 페스타' 개최 체험 행사",'https://example.org/a'),
              article("와인 맛보고 공연까지 이마트 '와인그랩 페스타' 연다",'https://example.org/b')]
        with patch('src.scouts.search_runtime.news',return_value=rows),patch('src.scouts.search_runtime.videos',return_value=[]) as videos:
            result=run_trend_scout(REQUEST)
        self.assertEqual(result['query_context']['video_search_queries'],['와인그랩 페스타','오프라인 체험 행사'])
        self.assertEqual(videos.call_count,2)

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

    def test_video_description_links_do_not_make_price_ads_event_references(self):
        row=dict(article('20대 한정 자동차 570만원','https://www.youtube.com/watch?v=abcdefghijk'),
                 source_type='youtube',description='관련 추천 영상: 팝업 체험 축제')
        with patch('src.scouts.search_runtime.news',return_value=[]),patch('src.scouts.search_runtime.videos',return_value=[row]):
            self.assertEqual(run_trend_scout(REQUEST)['insights'],[])

    def test_news_capacity_leaves_room_for_video_sources(self):
        rows = [article("스마트폰 팝업 체험", f"https://example.org/{i}") for i in range(12)]
        video = dict(article("스마트폰 팝업 체험", "https://www.youtube.com/watch?v=abcdefghijk"), source_type="youtube")
        with patch("src.scouts.search_runtime.news", return_value=rows), patch("src.scouts.search_runtime.videos", return_value=[video]):
            result = run_trend_scout(REQUEST)
        self.assertEqual(len(result["sources"]), 11)
        self.assertEqual(sum(s["source_type"] == "youtube" for s in result["sources"]), 1)
