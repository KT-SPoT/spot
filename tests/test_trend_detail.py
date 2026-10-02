"""Synthetic originals and cohort provenance; no provider requests."""
import copy
import json
import unittest
from datetime import date
from unittest.mock import patch

from src.scouts.trend import PATTERNS, run_trend_scout
from src.scouts.trend_detail import check_detail, audience_fit_questions, enrich_references
from src.scouts.search_runtime import SearchError
from src.graph.trend_context import build_trend_context
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.critic.semantic import build_input
from src.critic.critic import run_critic
from tests.test_trend_context import evidence
from tests.test_local import article

TITLE = '서울 게임 팝업 미션 체험'
SOURCE = {'source_id': 'S-T001', 'source_url': 'https://example.org/article'}
CASE = {'event_name': TITLE, 'source_ids': ['S-T001'], 'taxonomy_tags': ['photo_sharing']}
BODY = '참여자는 미션과 스탬프를 이용해 체험 공간을 이동하며 촬영 결과물을 비교하고 굿즈를 수집하는 프로그램을 경험한다.'


def html(body=BODY, title=TITLE, publication='2026-10-01', extra=''):
    meta = f'<meta property="article:published_time" content="{publication}">' if publication else ''
    return f'<html><head><meta property="og:title" content="{title}">{meta}</head><body>{extra}<article><p>{body}</p></article></body></html>'


def checked(document):
    return check_detail(CASE, SOURCE, PATTERNS, date(2026, 9, 1), date(2026, 10, 2),
                        fetcher=lambda _: (document, SOURCE['source_url']))


class TrendDetailTests(unittest.TestCase):
    def test_body_terms_retained_without_article_or_preference_claim(self):
        result = checked(html())
        self.assertEqual(result['status'], 'text_corroborated')
        self.assertIn('mission_journey', [m['mechanism'] for m in result['reported_mechanisms']])
        self.assertFalse(result['event_verified'])
        self.assertFalse(result['demographic_response_established'])
        self.assertNotIn(BODY, json.dumps(result, ensure_ascii=False))

    def test_navigation_terms_do_not_become_body_mechanisms(self):
        result = checked(html(body='행사에서는 직접 제품을 체험하며 기능의 차이를 비교하는 참여 프로그램이 진행된다고 관계자가 설명했다.',
                              extra='<nav><p>' + BODY + '</p></nav>'))
        self.assertEqual([m['mechanism'] for m in result['reported_mechanisms']], ['direct_product_trial'])

    def test_wrong_article_identity_is_unconfirmed(self):
        result = checked(html(title='전혀 다른 경제 기사'))
        self.assertEqual(result['reason'], 'ARTICLE_IDENTITY_NOT_MATCHED')
        self.assertEqual(result['reported_mechanisms'], [])

    def test_future_and_old_dates_are_rejected(self):
        for day in ('2026-10-03', '2025-01-01'):
            self.assertEqual(checked(html(publication=day))['reason'], 'ARTICLE_OUTSIDE_LOOKBACK')

    def test_conflicting_and_missing_dates_are_not_fabricated(self):
        self.assertEqual(checked(html(extra='<time datetime="2026-09-30"></time>'))['reason'], 'CONFLICTING_ARTICLE_DATES')
        result = checked(html(publication=None))
        self.assertEqual(result['status'], 'text_corroborated')
        self.assertIsNone(result['article_published_at'])

    def test_future_attendance_is_not_an_actual_response(self):
        result = checked(html(body=BODY + ' 방문객 10만 명을 목표로 진행할 예정이다.'))
        self.assertEqual(result['response_signals'], [])

    def test_reported_attendance_and_promotional_wording_are_limited(self):
        result = checked(html(body=BODY + ' 방문객 1,000명이 참여했다고 밝혔다. 큰 호응을 얻었다.'))
        self.assertEqual([s['kind'] for s in result['response_signals']], ['reported_attendance', 'promotional_response_wording'])
        self.assertFalse(result['demographic_response_established'])
        self.assertIn('미검증', result['response_signals'][0]['limitation'])

    def test_provider_exception_cannot_leak_credentials(self):
        for error, code in ((SearchError('SOURCE_UNAVAILABLE'), 'SOURCE_UNAVAILABLE'),
                            (ValueError('secret-value'), 'ARTICLE_PARSE_FAILED')):
            def fail(_):
                raise error
            result = check_detail(CASE, SOURCE, PATTERNS, date(2026, 9, 1), date(2026, 10, 2), fetcher=fail)
            self.assertEqual(result['reason'], code)
            self.assertNotIn('secret-value', json.dumps(result))

    def test_fit_is_mechanism_specific_and_missing_context_stays_empty(self):
        ctx = {'population_signals': [{'population_kind': 'sales', 'dominant_age': '60_plus',
                                      'dominant_gender': 'female', 'source_ids': ['Q1']}]}
        case = dict(CASE, case_detail=checked(html()))
        fit = audience_fit_questions(case, ctx)[0]
        self.assertIn('미션', fit['rationale'])
        self.assertIn('기능 비교 단계', fit['next_check'])
        self.assertEqual(fit['fit_status'], 'hypothesis_not_proven_preference')
        self.assertIsNone(fit['observed_profile']['reference_period'])
        self.assertEqual(fit['mechanism_source_ids'], ['S-T001'])
        self.assertEqual(audience_fit_questions(case, {}), [])

    def test_reader_budget_and_video_exclusion(self):
        cases = [dict(CASE, case_id=f'C{i}', source_ids=[f'S{i}']) for i in range(7)]
        output = {'sources': [dict(SOURCE, source_id=f'S{i}', source_type='youtube' if i == 0 else 'news') for i in range(7)],
                  'insights': cases, 'reference_cases': copy.deepcopy(cases), 'query_context': {}, 'warnings': []}
        with patch('src.scouts.trend_detail.check_detail', return_value=checked(html())) as reader:
            enrich_references(output, {}, PATTERNS, date(2026, 9, 1), date(2026, 10, 2), reader=reader)
        self.assertEqual(reader.call_count, 4)

    def test_default_off_and_offline_do_not_read_originals(self):
        request = evidence()['request']; request['research']['reference_date'] = '2026-10-01'
        with patch.dict('os.environ', {'SPOT_TREND_DETAIL_MODE': 'off', 'SPOT_SCOUT_MODE': 'live'}), \
             patch('src.scouts.search_runtime.news', return_value=[article(TITLE)]), \
             patch('src.scouts.search_runtime.videos', return_value=[]), \
             patch('src.scouts.trend.check_detail') as reader:
            self.assertEqual(run_trend_scout(request)['query_context']['detail_checks'], [])
            reader.assert_not_called()
            with patch.dict('os.environ', {'SPOT_TREND_DETAIL_MODE': 'article', 'SPOT_SCOUT_MODE': 'offline'}):
                run_trend_scout(request, detail_reader=reader)
                reader.assert_not_called()

    def test_brief_and_semantic_keep_provenance_and_omit_bad_fit(self):
        bundle = evidence(); bundle['request']['research']['reference_date'] = '2026-10-01'
        ctx = build_trend_context(bundle['request'], bundle['results']['quant'])
        with patch('src.scouts.search_runtime.news', return_value=[article(TITLE)]), \
             patch('src.scouts.search_runtime.videos', return_value=[]):
            def reader(case, source, patterns, start, end):
                return check_detail(case, source, patterns, start, end, fetcher=lambda _: (html(), source['source_url']))
            trend = run_trend_scout(bundle['request'], context=ctx, detail_reader=reader)
        bundle['results']['trend'] = trend
        bundle['module_status']['trend'] = trend['status']
        brief = generate_brief(bundle)
        card = next(c for c in brief['trend_patterns'] if c.get('type') == 'reference_case')
        self.assertTrue(card['audience_fit'])
        self.assertIn('본문 참여 방식 표현', render_markdown(brief))
        payload = build_input(bundle, run_critic(bundle))
        self.assertTrue(any(c['content'].get('audience_fit') for c in payload['claims'] if isinstance(c['content'], dict)))
        for fit in trend['insights'][0]['audience_fit']:
            fit['context_source_refs'] = [{'module': 'quant', 'source_id': 'missing'}]
        card = next(c for c in generate_brief(bundle)['trend_patterns'] if c.get('type') == 'reference_case')
        self.assertEqual(card['audience_fit'], [])
