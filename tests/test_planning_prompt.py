import copy
import unittest
from src.brief.handoff import render_handoff


class PlanningPromptTests(unittest.TestCase):
    def test_observations_links_and_proposals_are_separate(self):
        brief={'overview':{'area_summary':'지역 관측'},'unique_local_signals':[
            {'module':'quant','title':'연령 구성','shares':{'20s':{'share_pct':0},'60_plus':{'share_pct':72},'invalid':{'share_pct':float('nan')}},
             'reference_period':'2026-07','sources':[{'source_url':'https://public.example/data','title':'공공 관측'}]}],
            'local_changes':[{'title':'교통 기사','evidence':'도로 정비 후 통행을 재개했다.','published_at':'2026-05-01',
                              'sources':[{'source_url':'https://news.example/traffic','title':'교통 보도'}]}]}
        before=copy.deepcopy(brief)
        request={'store':{'name':'테스트 매장'},'campaign':{'product':'검토할 모델'}}
        result=render_handoff(brief,request)
        self.assertIn('20대 0%',result)
        self.assertIn('60대 이상 72%',result)
        self.assertNotIn('invalid',result)
        self.assertIn('보도된 내용:',result)
        self.assertIn('활용 힌트(기획 제안)',result)
        self.assertIn('2026-05-01',result)
        self.assertIn('https://public.example/data',result)
        self.assertIn('검토할 모델',result)
        self.assertEqual(brief['local_changes'],before['local_changes'])
        self.assertEqual(brief['unique_local_signals'][0]['reference_period'],'2026-07')

    def test_missing_inputs_remain_undecided_and_sources_are_safe(self):
        result=render_handoff({'local_changes':[{'title':'연결점이 약한 기사','evidence':'역사를 소개한다.',
            'sources':[{'source_url':'https://user:password@news.example/a'},{'source_url':'javascript:alert(1)'}]}]}, {})
        self.assertIn('정량 자료 미확보',result)
        self.assertIn('미정 — 사용자가 기획 단계에서 선택',result)
        self.assertIn('추가 배경 자료',result)
        self.assertIn('예산·인력·공간·기간',result)
        self.assertNotIn('password',result)
        self.assertNotIn('javascript:',result)
        self.assertIn('[조사자료 끝]',result)
