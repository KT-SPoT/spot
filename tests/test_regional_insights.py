import copy
import unittest
from unittest.mock import patch

from src.brief.regional_insights import regional_insights
from src.brief.experience_connections import connections
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.scouts.trend import build_queries, context_fit
from tests.test_trend_context import evidence


def timing(key):
    return {'module':'quant','population_kind':'sales','distribution_kind':'time','title':'시간대별 매출',
            'shares':{key:{'share_pct':48}},'sources':[{'source_id':'time','source_url':'https://public.example/time'}]}


class RegionalInsightTests(unittest.TestCase):
    def test_regional_timing_changes_search_without_assigning_age_preference(self):
        request=evidence()['request'];request['campaign']={'product':None}
        evening=regional_insights([timing('18_23')]);daytime=regional_insights([timing('14_18')])
        a=build_queries(request,{'regional_lenses':evening});b=build_queries(request,{'regional_lenses':daytime})
        self.assertNotEqual(a[0],b[0]);self.assertEqual(len(a),3)
        self.assertIn('저녁',a[0]);self.assertIn('비교',b[0])
        self.assertEqual(context_fit('20대 인기 팝업',{'population_signals':[{'population_kind':'sales','dominant_age':'20s'}]})[0],0)
        self.assertGreater(context_fit('저녁 팝업 직접 체험',{'regional_lenses':evening})[0],0)

    def test_reported_action_and_local_observation_are_both_required(self):
        case={'observation':'참여자가 미션을 수행하고 완료 결과를 확인한다.',
              'taxonomy_tags':['mission_journey'],'sources':[{'source_id':'trend'}]}
        local={'module':'local','title':'공원길 통행 재개','evidence':'도로 정비 후 통행을 재개했다.',
               'evidence_role':'surrounding_context','sources':[{'source_id':'local'}]}
        before=copy.deepcopy([case,local]);rows=connections(case,[],[local])
        self.assertIn('주변 행정구역 보도',rows[0]['statement'])
        self.assertEqual(rows[0]['context_source_refs'],[{'module':'local','source_id':'local'}])
        self.assertNotIn('방문객 증가',rows[0]['statement'])
        self.assertEqual(connections({**case,'observation':'전국 축제 개최'},[],[local]),[])
        self.assertEqual(connections(case,[],[{**local,'sources':[]}]),[])
        self.assertEqual(before,[case,local])

    def test_report_keeps_sources_without_diagnostic_failure_wording(self):
        bundle=evidence();brief=generate_brief(bundle)
        brief['needs_manual_check'].append('자료 미확보 및 근거 미확보 진단')
        text=render_markdown(brief)
        self.assertNotIn('미확보',text);self.assertIn('https://example.com/quant',text)
        self.assertIn('자료 미확보',brief['needs_manual_check'][-1])

    def test_video_library_survives_a_news_only_brief(self):
        from src.api.app import research_result
        bundle=evidence();brief=generate_brief(bundle)
        video={'source_url':'https://youtu.be/ABCDEFGHIJK','title':'체험 현장','source_id':'V-T-001'}
        run={'all_contracts_valid':True,'module_status':{},'state':{'research_brief':brief,'critic_result':{},
             'trend_result':{'sources':[],'reader_video_sources':[video]}}}
        with patch('src.integration_smoke.run_smoke',return_value=run):result=research_result(bundle['request'],mode='live')
        self.assertEqual(result['trend_discovery']['video_sources'],[video])
        run['state']['trend_result']['errors']=[{'provider':'videos','http_status':429,'code':'PROVIDER_HTTP_ERROR'}]
        with patch('src.integration_smoke.run_smoke',return_value=run):limited=research_result(bundle['request'],mode='live')
        self.assertEqual(limited['trend_discovery']['video_status'],'rate_limited')


if __name__=='__main__':unittest.main()
