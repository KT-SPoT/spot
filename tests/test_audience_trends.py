"""Synthetic regression cases for official observations and nationwide transfer."""
import copy
import json
import unittest
from unittest.mock import patch

from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.critic.critic import run_critic
from src.critic.semantic import build_input, PROMPT
from src.graph.trend_context import build_trend_context
from src.scouts.trend import run_trend_scout, build_queries
from tests.test_trend_context import evidence
from tests.test_local import article


def agency(bundle):
    q = bundle['results']['quant']
    q['sources'][0].update(source_name='소상공인365 상세분석', source_type='government',
                           source_url='https://bigdata.sbiz.or.kr/')
    q['metrics'].update(peak_floating_time_band='14_18', peak_sales_time_band='18_23',
                        peak_floating_day='sat', peak_sales_day='sun')
    q['insights'] = [{'claim_kind': 'public_api_observation', 'title': '공공 API 관측',
                     'metric_refs': ['dominant_floating_gender', 'dominant_floating_age',
                                     'peak_floating_time_band']}]
    return q


class AudienceTrendTests(unittest.TestCase):
    def test_nationwide_cross_industry_queries_do_not_use_site_or_device(self):
        bundle = evidence()
        ctx = build_trend_context(bundle['request'], bundle['results']['quant'])
        queries = build_queries(bundle['request'], ctx)
        self.assertEqual(len(queries), 3)
        self.assertTrue(all(any(c in q for q in queries) for c in ('게임', '음식', '축제')))
        self.assertNotIn('부산', ' '.join(queries))
        self.assertNotIn('폴드', ' '.join(queries))
        self.assertNotIn('Galaxy', ' '.join(queries))
        self.assertNotIn('30대', ' '.join(queries))
        self.assertNotIn('40대', ' '.join(queries))
        swapped = copy.deepcopy(ctx)
        for p in swapped['population_signals']:
            p['dominant_gender'] = 'female' if p['dominant_gender'] == 'male' else 'male'
        self.assertEqual(queries, build_queries(bundle['request'], swapped))

    def test_game_food_festival_in_other_regions_survive_with_transfer_questions(self):
        bundle = evidence(); agency(bundle)
        bundle['request']['research']['reference_date'] = '2026-10-01'
        ctx = build_trend_context(bundle['request'], bundle['results']['quant'])
        rows = [article('서울 게임사 별빛 팝업 미니게임 체험 후기', 'https://example.org/game'),
                article('대구 음식 팝업 시식 사진 체험', 'https://example.org/food'),
                article('제주 지역 축제 스탬프 미션 참여', 'https://example.org/festival'),
                article('갤럭시 폴드8 온라인 언박싱 최저가', 'https://example.org/commerce')]
        with patch('src.scouts.search_runtime.news', return_value=rows) as news, \
             patch('src.scouts.search_runtime.videos', return_value=[]) as videos:
            trend = run_trend_scout(bundle['request'], context=ctx)
        self.assertEqual((news.call_count, videos.call_count), (3, 3))
        self.assertEqual({c['event_category'] for c in trend['reference_cases']}, {'game', 'food', 'festival'})
        self.assertTrue(all(c['request_relevance'] == 'cross_industry_transfer' for c in trend['insights']))
        for case in trend['reference_cases']:
            self.assertEqual(case['verification_status'], 'candidate')
            self.assertTrue(case['adaptation_hypotheses'])
            self.assertIn('탐색 가설', case['audience_hypothesis'])
            self.assertTrue(all('Galaxy Z Fold8' in h['statement'] for h in case['adaptation_hypotheses']))
            self.assertIn({'module': 'quant', 'source_id': 'quant-source'}, case['context_source_refs'])
        bundle['results']['trend'] = trend
        bundle['module_status']['trend'] = trend['status']
        text = render_markdown(generate_brief(bundle))
        self.assertIn('매장 응용 가설', text)
        self.assertIn('제주', text)
        payload = build_input(bundle, run_critic(bundle))
        claim = next(c for c in payload['claims'] if c['claim_id'].startswith('trend:'))
        self.assertIn('adaptation_hypotheses', claim['content'])
        self.assertIn('TREND is nationwide and cross-industry', PROMPT)

    def test_reference_selection_keeps_categories_instead_of_only_top_duplicates(self):
        bundle = evidence()
        rows = [article('서울 게임 팝업 미니게임 체험 촬영 스탬프', f'https://example.org/game/{i}') for i in range(7)]
        rows += [article('대구 음식 팝업 시식', 'https://example.org/food'),
                 article('제주 축제 스탬프', 'https://example.org/festival')]
        with patch('src.scouts.search_runtime.news', return_value=rows), \
             patch('src.scouts.search_runtime.videos', return_value=[]):
            result = run_trend_scout(bundle['request'])
        self.assertEqual(len(result['reference_cases']), 3)
        self.assertEqual({c['event_category'] for c in result['reference_cases']}, {'game', 'food', 'festival'})

    def test_official_demographic_and_peak_values_are_cards_without_llm_reapproval(self):
        bundle = evidence(); q = agency(bundle)
        brief = generate_brief(bundle)
        cards = {m: c for c in brief['unique_local_signals'] if c.get('module') == 'quant'
                 for m in c.get('metric_refs', [])}
        self.assertEqual(cards['peak_floating_time_band']['value'], '14~18시')
        self.assertEqual(cards['dominant_floating_age']['value'], '30대')
        self.assertEqual(cards['peak_sales_day']['value'], '일요일')
        self.assertEqual(cards['dominant_floating_gender']['evidence_basis'], 'public_agency_api')
        self.assertIsNone(cards['peak_floating_time_band']['reference_period'])
        self.assertIn('14~18시', render_markdown(brief))
        payload = build_input(bundle, run_critic(bundle))
        self.assertFalse(any(c['claim_id'].startswith('quant:') for c in payload['claims']))
        self.assertEqual(len(payload['accepted_quant_observations']), 1)
        self.assertTrue(payload['quant_facts'])
        # A separately worded inference remains reviewable with an agency source.
        q['insights'].append({'title': '고객 선호 가설', 'claim_kind': 'inference',
                              'evidence': '30대가 게임을 선호한다',
                              'metric_refs': ['dominant_floating_age']})
        payload = build_input(bundle, run_critic(bundle))
        self.assertEqual(len([c for c in payload['claims'] if c['claim_id'].startswith('quant:')]), 1)
        # A source that merely calls itself official cannot gain trust by name.
        q['sources'][0]['source_url'] = 'https://example.org/not-the-agency'
        payload = build_input(bundle, run_critic(bundle))
        self.assertEqual(payload['accepted_quant_observations'], [])

    def test_context_uses_matching_archive_shares_and_peak_times_without_raw_html(self):
        bundle = evidence(); q = agency(bundle)
        selected = {'male': {'count': 60, 'share_pct': 60}, 'female': {'count': 40, 'share_pct': 40},
                    '30s': {'count': 40, 'share_pct': 40}, '40s': {'count': 35, 'share_pct': 35}}
        population = {'derived_selected_area': {'latest_monthly_daily_flow_population': 1000},
                      'floating_population': {'demographics': {'regions': {'선택 영역': selected}}},
                      'resident_population': {'demographics': {'regions': {'선택 영역': selected}}}}
        archive = {'analysis': {'lat': 35.0, 'lng': 129.0, 'radius_m': 1000, 'upjong_cd': 'G20802'},
                   'analy_date': '20261001', 'reports': {4: {'html': 'SYNTHETIC_RAW_HTML'}}}
        with patch('src.brief.quant_evidence.parse_population_report', return_value=population):
            ctx = build_trend_context(bundle['request'], q, quant_evidence=archive)
            self.assertEqual(ctx['population_signals'][0]['shares']['male']['share_pct'], 60)
            self.assertIn('resident_population', [p['population_kind'] for p in ctx['population_signals']])
            self.assertIsNone(ctx['population_signals'][0]['reference_period'])
            self.assertEqual(ctx['timing_signals'][0]['peak_time_band'], '14_18')
            self.assertNotIn('SYNTHETIC_RAW_HTML', json.dumps(ctx))
            wrong = copy.deepcopy(archive); wrong['analysis']['lat'] = 36.0
            with self.assertRaises(ValueError):
                build_trend_context(bundle['request'], q, quant_evidence=wrong)
