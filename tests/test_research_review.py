"""Geographic Critic compatibility path, source integrity and graceful failure."""
import copy,json,unittest
from unittest.mock import patch
from src.critic.research_review import build_research_input,validate_research_response
from src.critic.semantic import run_semantic,SemanticError
from src.critic.critic import run_critic
from src.scouts.trend import run_trend_scout
from src.graph.trend_context import build_trend_context
from src.brief.generator import generate_brief
from tests.test_trend_context import evidence
from tests.test_local import article

def bundle():
    r=evidence();r['request']['research']['reference_date']='2026-10-01'
    context=build_trend_context(r['request'],r['results']['quant'])
    with patch('src.scouts.search_runtime.news',return_value=[article('제주 축제 미션 팝업 체험')]),patch('src.scouts.search_runtime.videos',return_value=[]):
        r['results']['trend']=run_trend_scout(r['request'],context=context)
    r['module_status']['trend']=r['results']['trend']['status'];return r

def answer(p):
    return {'reviews':[{'case_id':c['case_id'],'verdict':'within_scope','reason':'전국 사례로 설명되어 지역 혼입이 없습니다.','suggestion':'현재 지역 범위 표현을 유지합니다.'} for c in p['cases']]}

class ResearchReviewTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict('os.environ',{'SPOT_CRITIC_PROFILE':'research','SPOT_SCOUT_MODE':'live'});env.start();self.addCleanup(env.stop)
        self.bundle=bundle();self.critic=run_critic(self.bundle);self.payload=build_research_input(self.bundle,self.critic)
    def test_nationwide_reference_needs_no_originality_or_demographic_match(self):
        before=copy.deepcopy(self.bundle)
        r=run_semantic(self.bundle,self.critic,caller=answer,mode='shadow')
        self.assertTrue(r['performed']);self.assertEqual(r['call_count'],1)
        self.assertEqual(r['case_reviews'][0]['scope_verdict'],'within_scope')
        self.assertEqual(r['case_reviews'][0]['verdict'],'useful')
        self.assertEqual(r['case_reviews'][0]['source_ids'],self.bundle['results']['trend']['insights'][0]['source_ids'])
        self.assertEqual(before,self.bundle)
    def test_incomplete_duplicate_unknown_and_extra_fields_rejected(self):
        raw=answer(self.payload);unknown=copy.deepcopy(raw);unknown['reviews'][0]['case_id']='unknown'
        extra=copy.deepcopy(raw);extra['reviews'][0]['source_ids']=['invented']
        for bad in ({'reviews':[]},{'reviews':raw['reviews']*2},unknown,extra):
            with self.assertRaises(SemanticError):validate_research_response(bad,self.payload)
    def test_local_misattribution_removes_only_adaptation_not_nationwide_source(self):
        def judge(p):
            r=answer(p);r['reviews'][0].update(verdict='scope_confusion',reason='전국 참여 반응을 현지 반응으로 표현했습니다.',suggestion='전국 사례로 표현합니다.');return r
        r=run_semantic(self.bundle,self.critic,caller=judge,mode='shadow')
        self.critic['checks']['semantic_review']=r
        b=generate_brief(self.bundle,self.critic)
        cases=[c for c in b['trend_patterns'] if c.get('type')=='reference_case']
        self.assertTrue(cases[0]['sources']);self.assertFalse(cases[0]['adaptation_hypotheses'])
    def test_bounded_payload_and_provider_failure_do_not_leak(self):
        self.assertLess(len(json.dumps(self.payload,ensure_ascii=False).encode()),60000)
        self.assertNotIn('source_url',str(self.payload))
        def fail(p):raise RuntimeError('private-key-example')
        r=run_semantic(self.bundle,self.critic,caller=fail,mode='shadow')
        self.assertFalse(r['performed']);self.assertNotIn('private-key-example',str(r))
    def test_disabled_review_does_not_call_model(self):
        with patch('src.critic.research_review.run_research_review') as model:
            self.assertEqual(run_semantic(self.bundle,self.critic,mode='off')['code'],'DISABLED');model.assert_not_called()
if __name__=='__main__':unittest.main()
