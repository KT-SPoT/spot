import copy
import unittest

from src.brief.connection_synthesis import (build_connection_input,
    run_connection_synthesis, apply_connection_synthesis, resolve_connection_draft)
from src.brief.synthesis import apply_synthesis, run_synthesis
from src.critic.semantic import SemanticError
from tests.test_regional_synthesis import brief, answer, review, source


class ConnectionSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.brief=brief()
        self.brief['local_changes']=[{'module':'local','title':'통행 재개 보도',
            'evidence':'명륜동 방향 차량 통행을 재개했다.', 'published_at':'2026-05-18',
            'change_state':'reported_repair_or_reopening','evidence_role':'direct_change',
            'scope':'보도된 도로 구간','sources':[source('local')]}]
        self.base=run_synthesis(self.brief,caller=lambda p:answer(p,links=False),reviewer=review)

    def connection(self,payload):
        row=answer(payload)['insights'][0]
        row.update(insight_id='C1',evidence_ids=['E00'],
            title='매출 요일 후보에서 직접 비교하는 참여 방식',
            interpretation='토요일의 체험 접점을 검토할 때 전국 행사의 직접 사용·비교 방식을 참고할 수 있습니다.')
        local=copy.deepcopy(row)
        local.update(insight_id='C2',evidence_ids=['E02'],experience_links=[],
            title='통행 재개 보도에서 읽을 방문 안내 접점',
            interpretation='보도된 도로 구간을 매장 방문 안내 자료와 대조할 수 있습니다.',
            planning_question='위치 안내와 제품 체험 안내를 나누어 검토할까요?',
            counterpoint='2026년 5월 보도한 통행 재개이며 매출 증가를 설명하는 자료는 아닙니다.')
        return {'insights':[row,local]}

    def test_reviewed_baseline_and_local_dates_are_sent_without_old_case_claims(self):
        payload=build_connection_input(self.brief,self.base,reference_date='2026-10-04')
        self.assertEqual(payload['planning_lenses'][0]['evidence_ids'],['E00','E01'])
        self.assertEqual(payload['local_reading_notes'][0]['published_at'],'2026-05-18')
        self.assertEqual(payload['local_reading_notes'][0]['reported_stage'],'reported_repair_or_reopening')
        self.assertEqual(payload['reference_date'],'2026-10-04')
        self.assertNotIn('source_url',str(payload))

    def test_model_selects_reviewed_lens_and_code_resolves_exact_evidence_ids(self):
        p=build_connection_input(self.brief,self.base)
        candidate=self.connection(p)['insights'][0]
        draft={k:copy.deepcopy(candidate[k]) for k in ('title','interpretation','planning_question','counterpoint','search_terms')}
        draft.update(planning_lens_id=self.base['insights'][0]['insight_id'],
            action_id=p['experience_actions'][0]['action_id'],why_this_case='직접 사용 과제를 비교하는 참고 방식입니다.',
            comparison_question='설명 위주와 직접 사용해보는 방식을 어떻게 비교할까요?')
        raw={'local_reading':None,'case_connections':[draft]}
        resolved=resolve_connection_draft(raw,p)
        self.assertEqual(resolved['insights'][0]['evidence_ids'],['E00','E01'])
        raw['case_connections'][0]['planning_lens_id']='unreviewed'
        with self.assertRaises(SemanticError):resolve_connection_draft(raw,p)

    def test_additions_preserve_baseline_and_resolve_each_scout_source(self):
        before=copy.deepcopy(self.brief);calls=[]
        def generate(p):calls.append('connections');return self.connection(p)
        def judge(p):calls.append('review');return review(p,generic=True)
        result=run_connection_synthesis(self.brief,self.base,caller=generate,reviewer=judge)
        applied=apply_connection_synthesis(self.brief,self.base,result)
        self.assertEqual(calls,['connections','review'])
        self.assertEqual(result['call_count'],2);self.assertEqual(result['scout_call_count'],0)
        self.assertEqual(applied['research_implications'][0],apply_synthesis(self.brief,self.base)['research_implications'][0])
        self.assertEqual(len(applied['research_implications']),3)
        self.assertEqual(applied['research_implications'][1]['contribution'],'baseline')
        self.assertEqual(applied['research_implications'][2]['basis'][0],self.brief['local_changes'][0])
        self.assertIn('보도: 2026-05-18',applied['research_implications'][2]['observation'])
        case=applied['trend_patterns'][0]
        self.assertEqual(case['sources'],self.brief['trend_patterns'][0]['sources'])
        self.assertEqual(case['adaptation_hypotheses'][0]['context_source_refs'],[{'module':'quant','source_id':'quant-1'}])
        self.assertEqual(self.brief,before)

    def test_weak_connection_does_not_erase_quant_baseline_or_local_reading(self):
        result=run_connection_synthesis(self.brief,self.base,caller=self.connection,reviewer=lambda p:review(p,weak=True))
        applied=apply_connection_synthesis(self.brief,self.base,result)
        self.assertEqual(len(applied['research_implications']),2)
        self.assertEqual(applied['trend_patterns'][0]['adaptation_hypotheses'],[])
        self.assertTrue(applied['trend_patterns'][0]['sources'])

    def test_reviewer_receives_only_each_candidates_attached_observations(self):
        received=[]
        def judge(payload):received.append(payload);return review(payload)
        result=run_connection_synthesis(self.brief,self.base,caller=self.connection,reviewer=judge)
        self.assertTrue(result['performed'])
        self.assertNotIn('observations',received[0])
        self.assertEqual([r['evidence_id'] for r in received[0]['candidate_contexts'][0]['observations']],['E00'])
        self.assertEqual([r['evidence_id'] for r in received[0]['candidate_contexts'][1]['observations']],['E02'])
        self.assertEqual(received[0]['candidate_contexts'][1]['experience_actions'],[])

    def test_baseline_or_source_changes_require_new_connection_review(self):
        result=run_connection_synthesis(self.brief,self.base,caller=self.connection,reviewer=review)
        changed=copy.deepcopy(self.base)
        changed['insights'][0]['planning_question']='매장 안내와 직접 비교를 어떻게 나눌까요?'
        with self.assertRaisesRegex(SemanticError,'STALE_CONNECTION_INPUT|UNREVIEWED_SYNTHESIS'):
            apply_connection_synthesis(self.brief,changed,result)
        changed_brief=copy.deepcopy(self.brief)
        changed_brief['local_changes'][0]['published_at']='2026-05-19'
        with self.assertRaises(SemanticError):apply_connection_synthesis(changed_brief,self.base,result)

    def test_missing_additional_context_and_unreviewed_baseline_do_not_call(self):
        calls=[]
        absent=run_connection_synthesis(self.brief,{'performed':False},caller=lambda p:calls.append(p))
        self.assertEqual(absent['code'],'NO_REVIEWED_BASELINE')
        bare=brief();bare['trend_patterns']=[]
        base=run_synthesis(bare,caller=lambda p:answer(p,links=False),reviewer=review)
        absent=run_connection_synthesis(bare,base,caller=lambda p:calls.append(p))
        self.assertEqual(absent['code'],'NO_ADDITIONAL_CONTEXT');self.assertEqual(calls,[])

    def test_past_traffic_record_is_not_a_current_operating_instruction(self):
        def generate(p):
            raw=self.connection(p)
            raw['insights'][1]['planning_question']='통행 재개 시각에 맞춰 방문 안내를 활성화할까요?'
            return raw
        result=run_connection_synthesis(self.brief,self.base,reference_date='2026-10-07',
                                         caller=generate,reviewer=review)
        self.assertEqual(len(result['insights']),1)
        self.assertEqual(result['context_rejections'][0]['code'],'LOCAL_RECORD_USED_AS_CURRENT_CONTEXT')
        def valid(p):
            raw=generate(p)
            raw['insights'][1]['planning_question']='당시 보도된 경로를 현재 방문 안내 자료와 대조할까요?'
            return raw
        result=run_connection_synthesis(self.brief,self.base,reference_date='2026-10-07',
                                         caller=valid,reviewer=review)
        self.assertEqual(len(result['insights']),2)


if __name__=='__main__':unittest.main()
