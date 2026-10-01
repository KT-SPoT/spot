"""Context provenance, graph scheduling and relevance; no provider calls."""
import copy
import threading
import unittest
from unittest.mock import patch

from src.graph.graph import build_graph
from src.graph.trend_context import build_trend_context
from src.scouts.trend import run_trend_scout, build_queries
from src.scouts.trend_relevance import find_product_match, contains_brand_term, get_brand_hint, score_candidate_relevance
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from tests.test_research_brief import fixture
from tests.test_local import article


def evidence():
    bundle = fixture()
    bundle['request'].update(campaign={'product':'Galaxy Z Fold8'}, store={'name':'KT플라자 명지', 'address':'부산광역시 강서구'})
    quant, local = bundle['results']['quant'], bundle['results']['local']
    quant['metrics'].update(dominant_floating_gender='male', dominant_floating_age='30s',
                            dominant_sales_gender='female', dominant_sales_age='40s')
    local['insights'][0].update(verification_status='context_corroborated', evidence='문화 공원 계획',
                                evidence_role='surrounding_context')
    return bundle


class TrendContextTests(unittest.TestCase):
    def test_cohorts_provenance_missing_shares_and_no_mutation(self):
        bundle = evidence(); before = copy.deepcopy(bundle)
        ctx = build_trend_context(bundle['request'],bundle['results']['quant'],bundle['results']['local'])
        self.assertEqual([p['population_kind'] for p in ctx['population_signals']], ['floating_population','sales'])
        self.assertEqual(ctx['population_signals'][0]['dominant_age'],'30s')
        self.assertIsNone(ctx['population_signals'][0]['gender_share_pct'])
        self.assertIsNone(ctx['population_signals'][0]['reference_period'])
        self.assertNotIn('source_url',ctx['sources']['quant'][0])
        self.assertEqual(ctx['local_signals'][0]['evidence_role'],'surrounding_context')
        self.assertEqual(bundle,before)

    def test_failed_mismatched_mock_and_uncorroborated_context(self):
        for change in ({'status':'failed'},{'request_id':'other'},{'warnings':['MOCK_ONLY_NOT_REAL_DATA']}):
            bundle=evidence(); bundle['results']['quant'].update(change)
            ctx=build_trend_context(bundle['request'],bundle['results']['quant'],bundle['results']['local'])
            self.assertEqual(ctx['population_signals'],[])
        bundle=evidence(); bundle['results']['local']['insights'][0]['verification_status']='unconfirmed'
        self.assertEqual(build_trend_context(bundle['request'],local=bundle['results']['local'])['local_signals'],[])

    def test_graph_parallel_barrier_and_complete_context_once(self):
        bundle=evidence(); arrived=threading.Barrier(2)
        def runner(module):
            def run(request):
                arrived.wait(timeout=5)
                return bundle['results'][module]
            return run
        with patch('src.graph.graph.run_quant_scout',side_effect=runner('quant')), patch('src.graph.graph.run_local_scout',side_effect=runner('local')), patch('src.graph.graph.run_trend_scout',return_value=bundle['results']['trend']) as trend:
            result=build_graph().invoke({'request':bundle['request']})
        trend.assert_called_once_with(bundle['request'],context=result['trend_context'])
        self.assertEqual(len(result['trend_context']['population_signals']),2)
        self.assertEqual(len(result['trend_context']['local_signals']),1)

    def test_age_query_bounded_soft_ranking_and_cited_brief(self):
        bundle=evidence(); request=bundle['request']
        ctx=build_trend_context(request,bundle['results']['quant'],bundle['results']['local'])
        self.assertEqual(len(build_queries(request,ctx)),3)
        self.assertIn('30대',build_queries(request,ctx)[-1])
        rows=[article('갤럭시 Z 폴드8 팝업 체험','https://example.org/a'),
              article('갤럭시 Z 폴드8 팝업 체험 30대 남성 문화 공원','https://example.org/b'),
              article('화장품 팝업 30대 남성 문화 공원','https://example.org/c')]
        with patch('src.scouts.search_runtime.news',return_value=rows) as news, patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(request,context=ctx)
        self.assertEqual(news.call_count,3)
        self.assertEqual(len(result['insights']),2)
        self.assertIn('30대',result['reference_cases'][0]['event_name'])
        self.assertEqual({r['module'] for r in result['reference_cases'][0]['context_source_refs']},{'quant','local'})
        bundle['results']['trend']=result
        brief=generate_brief(bundle); text=render_markdown(brief)
        refs=[c for c in brief['trend_patterns'] if c.get('type')=='reference_case']
        self.assertEqual(len(refs),2)
        self.assertIn('quant',refs[0]['context_sources'])
        self.assertIn('선정 이유',text)
        self.assertIn('실제 행사 참여자의 성별·연령',text)
        self.assertEqual(brief['source_count'],4)

    def test_single_candidate_in_brief_without_repeated_pattern(self):
        bundle=evidence()
        with patch('src.scouts.search_runtime.news',return_value=[article('갤럭시 폴드8 팝업 체험')]), patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(bundle['request'])
        self.assertEqual(result['patterns'],[])
        bundle['results']['trend']=result
        brief=generate_brief(bundle)
        self.assertEqual(len(brief['trend_patterns']),1)
        self.assertIn('체험 패턴 0개·참고 후보 1건',brief['overview']['area_summary'])

    def test_library_does_not_replace_search_failures(self):
        bundle=evidence()
        with patch('src.scouts.search_runtime.news',return_value=[]), patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(bundle['request'])
        self.assertTrue(result['reference_library'])
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['sources'],[])
        bundle['results']['trend']=result
        self.assertEqual(generate_brief(bundle)['trend_patterns'],[])

    def test_model_boundary_brand_and_timestamp(self):
        self.assertEqual(find_product_match('갤럭시 폴드8 팝업','갤럭시폴드8팝업','Galaxy Z Fold8')[0],'exact')
        self.assertEqual(find_product_match('갤럭시 폴드80 팝업','갤럭시폴드80팝업','Galaxy Z Fold8')[0],'none')
        self.assertFalse(contains_brand_term('skt 팝업','KT'))
        self.assertEqual(get_brand_hint(evidence()['request']),'KT')
        with patch('src.scouts.search_runtime.news',return_value=[article('갤럭시 폴드8 팝업 체험 타임 스탬프')]), patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(evidence()['request'])
        self.assertNotIn('mission_journey',result['insights'][0]['taxonomy_tags'])

    def test_broken_context_refs_do_not_promote_context_reasoning(self):
        bundle=evidence()
        with patch('src.scouts.search_runtime.news',return_value=[article('갤럭시 폴드8 팝업 체험')]), patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(bundle['request'])
        result['insights'][0].update(context_source_refs=[{'module':'quant','source_id':'missing'}],why_relevant=['unsupported'])
        bundle['results']['trend']=result
        brief=generate_brief(bundle)
        self.assertNotIn('unsupported',render_markdown(brief))

    def test_review_commerce_penalties_and_reference_cap(self):
        request=evidence()['request']
        plain=score_candidate_relevance({'title':'갤럭시 폴드8 팝업 체험'},request)
        review=score_candidate_relevance({'title':'갤럭시 폴드8 팝업 체험 리뷰 사용기 가격 최저가'},request)
        self.assertLess(review['relevance_score'],plain['relevance_score'])
        self.assertFalse(review['is_experiential_candidate'])
        rows=[article('갤럭시 폴드8 팝업 체험',f'https://example.org/{i}') for i in range(8)]
        with patch('src.scouts.search_runtime.news',return_value=rows), patch('src.scouts.search_runtime.videos',return_value=[]):
            result=run_trend_scout(request)
        self.assertEqual(len(result['reference_cases']),5)

    def test_failed_quant_keeps_local_context_and_continues(self):
        bundle=evidence(); bundle['results']['quant']['status']='failed'
        with patch('src.graph.graph.run_quant_scout',return_value=bundle['results']['quant']), patch('src.graph.graph.run_local_scout',return_value=bundle['results']['local']), patch('src.graph.graph.run_trend_scout',return_value=bundle['results']['trend']) as trend:
            result=build_graph().invoke({'request':bundle['request']})
        self.assertEqual(result['trend_context']['population_signals'],[])
        self.assertEqual(len(result['trend_context']['local_signals']),1)
        trend.assert_called_once()
