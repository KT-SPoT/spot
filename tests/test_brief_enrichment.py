"""Enrichment through the real API runner; all provider inputs are synthetic."""
import copy
import json
import unittest
from unittest.mock import patch

from src.api.app import research_result
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.brief.trend_groups import group_coverage
from tests.test_research_brief import fixture


def candidates(bundle):
    trend = bundle['results']['trend']
    names = ["KT, '별빛친구 X 달빛친구' 팝업 체험", "KT, 별빛친구 협업 팝업 운영",
             "다른브랜드, '다른친구' 팝업 체험"]
    trend['sources'] = [dict(trend['sources'][0], source_id=f't{i}', source_url=f'https://example.com/trend/{i}') for i in range(3)]
    trend['insights'] = [dict(case_id=f'c{i}', source_ids=[f't{i}'], event_name=name,
                             origin='live_search_candidate', published_at='2026-08-05',
                             location=None, taxonomy_tags=['direct_product_trial']) for i, name in enumerate(names)]
    trend['reference_cases'] = copy.deepcopy(trend['insights'])
    trend['reference_patterns'] = [dict(pattern_id='direct_product_trial', name='제품 체험',
                                      verification_status='candidate', example_case_ids=['c0', 'c1', 'c2'],
                                      example_source_ids=['t0', 't1', 't2'])]
    return trend


class BriefEnrichmentTests(unittest.TestCase):
    def test_related_reports_group_without_dropping_sources_or_mutating_scout(self):
        bundle = fixture(); candidates(bundle); before = copy.deepcopy(bundle)
        brief = generate_brief(bundle)
        refs = [c for c in brief['trend_patterns'] if c.get('type') == 'reference_case']
        pattern = brief['trend_patterns'][0]
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0]['article_count'], 2)
        self.assertEqual({s['source_id'] for s in refs[0]['sources']}, {'t0', 't1'})
        self.assertEqual((pattern['evidence_count'], pattern['article_count']), (2, 3))
        self.assertIn('동일 행사 여부', render_markdown(brief))
        self.assertEqual(brief['source_count'], 5)
        self.assertEqual(bundle, before)

    def test_same_event_coverage_alone_does_not_establish_repeated_pattern(self):
        bundle = fixture(); trend = candidates(bundle)
        trend['insights'] = trend['insights'][:2]
        trend['reference_cases'] = trend['reference_cases'][:2]
        trend['reference_patterns'][0].update(example_case_ids=['c0', 'c1'], example_source_ids=['t0', 't1'])
        cards = generate_brief(bundle)['trend_patterns']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['type'], 'reference_case')

    def test_missing_dates_different_places_and_generic_terms_remain_separate(self):
        for field, value in [('published_at', None), ('published_at', '2026-08-06'), ('location', '다른 장소')]:
            items = candidates(fixture())['insights'][:2]
            items[1][field] = value
            self.assertEqual(len(group_coverage(items)), 2)
        items = candidates(fixture())['insights'][:2]
        items[0]['event_name'] = "KT, '갤럭시' 팝업 체험"
        items[1]['event_name'] = "KT, 갤럭시 팝업 운영"
        self.assertEqual(len(group_coverage(items)), 2)

    def test_api_runner_retains_same_run_demographics_without_returning_html(self):
        bundle = fixture(); request = bundle['request']
        request['store'].update(name='합성점', lat=35.0, lng=129.0)
        request['campaign'] = {'product': '합성 제품', 'purpose': '합성 조사'}
        selected = {'male': {'count': 600, 'share_pct': 60}, 'female': {'count': 400, 'share_pct': 40},
                    '40s': {'count': 200, 'share_pct': 20}}
        population = {'derived_selected_area': {'latest_monthly_daily_flow_population': 1000},
                      'floating_population': {'monthly_daily_average': {'periods': ['26.06']},
                                              'demographics': {'regions': {'선택 영역': selected}}}}
        archive = {'analysis': {'lat': 35.0, 'lng': 129.0, 'radius_m': 1000, 'upjong_cd': 'G20802'},
                   'analy_date': '20261001', 'reports': {4: {'html': 'synthetic-raw-provider-html'}}}
        sections = {'industry': {}, 'sales': {}, 'population': population, 'area': {}}
        with patch.dict('os.environ', {'SBIZ365_CERT_KEY': 'synthetic-only'}), \
             patch('src.scouts.quant.load_dotenv'), \
             patch('src.scouts.quant.collect_sbiz365_reports', return_value=archive) as collect, \
             patch('src.scouts.quant._parse_reports', return_value=(sections, [], [])), \
             patch('src.brief.quant_evidence.parse_population_report', return_value=population), \
             patch('src.graph.graph.run_local_scout', return_value=bundle['results']['local']), \
             patch('src.graph.graph.run_trend_scout', return_value=bundle['results']['trend']):
            result = research_result(request, mode='live')
        cards = [c for c in result['research_brief']['unique_local_signals'] if 'shares' in c]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['shares']['male']['share_pct'], 60)
        self.assertIsNone(cards[0]['reference_period'])  # Monthly trend date is not the demographics date.
        self.assertNotIn('synthetic-raw-provider-html', json.dumps(result))
        collect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
