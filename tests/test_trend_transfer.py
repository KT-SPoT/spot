"""Audience coverage and transfer design changes, not invented preferences."""
from copy import deepcopy
import json
import unittest

from src.scouts.trend_transfer import audience_lenses
from src.scouts.trend_detail import audience_fit_questions
from src.evaluation.trend_audience import evaluate_context_contrasts, replay, profile, compare
from src.brief.generator import generate_brief
from src.critic.critic import run_critic
from src.critic.research_review import build_research_input
from tests.test_trend_audience_evaluation import inputs
from tests.test_trend_context import evidence


def full_profile(kind='floating_population'):
    return {'population_kind':kind, 'dominant_age':'40s', 'dominant_gender':'male',
            'source_ids':['quant-source'], 'age_share_pct':30, 'gender_share_pct':55,
            'shares': {'40s':{'share_pct':30}, '20s':{'share_pct':25},
                       '30s':{'share_pct':20}, '60_plus':{'share_pct':25},
                       'male':{'share_pct':55}, 'female':{'share_pct':45}}}


class TransferTests(unittest.TestCase):
    def test_full_distribution_drives_coverage_not_age_or_gender_preferences(self):
        base=full_profile(); changed=deepcopy(base)
        changed['dominant_age']='60_plus'; changed['dominant_gender']='female'
        # Names alone cannot change comparison design or assign an industry.
        self.assertEqual(audience_lenses(base,{}),audience_lenses(changed,{}))
        changed['shares'].update({'40s':{'share_pct':10}, '20s':{'share_pct':15},
                                 '30s':{'share_pct':15}, '60_plus':{'share_pct':60}})
        lenses=audience_lenses(changed,{})
        self.assertEqual(lenses[0]['rule'],'concentrated')
        self.assertNotEqual(lenses[0]['question'],audience_lenses(base,{})[0]['question'])
        self.assertNotIn('뷰티',json.dumps(lenses,ensure_ascii=False))

    def test_missing_partial_and_invalid_shares_do_not_prove_distribution(self):
        for shares in ({}, {'20s':{'share_pct':40}, '40s':{'share_pct':35}},
                       {'20s':{'share_pct':True}, '40s':{'share_pct':float('nan')}},
                       {'20s':{'share_pct':-10}, '40s':{'share_pct':110}}):
            p=full_profile(); p['shares']=shares
            self.assertEqual(audience_lenses(p,{})[0]['rule'],'distribution_unavailable')

    def test_peak_alignment_changes_flow_question_and_retains_both_sources(self):
        context={'timing_signals':[{'population_kind':k,'peak_day':'sat',
            'peak_time_band':'09_12','source_ids':[sid]} for k,sid in
            [('floating_population','Q-flow'),('sales','Q-sales')]]}
        lens=audience_lenses(full_profile(),context)[-1]
        self.assertEqual(lens['rule'],'flow_sales_align')
        self.assertIn('09~12시',lens['observation'])
        context['timing_signals'][1]['peak_time_band']='18_23'
        changed=audience_lenses(full_profile(),context)[-1]
        self.assertEqual(changed['rule'],'flow_sales_differ')
        self.assertNotEqual(lens['question'],changed['question'])
        self.assertEqual({r['source_id'] for r in changed['context_source_refs']},{'Q-flow','Q-sales'})
        context['timing_signals'][1]['peak_time_band']='invented-band'
        self.assertEqual(audience_lenses(full_profile(),context)[-1]['rule'],'flow_sales_align')
        context['timing_signals'][0]['reference_period']='2026-07'
        context['timing_signals'][1]['reference_period']='2026-08'
        self.assertEqual(audience_lenses(full_profile(),context)[-1]['rule'],'single_population_peak')

    def test_scheduled_surrounding_housing_stays_context_not_store_demand(self):
        ctx={'local_signals':[{'title':'아파트 입주 예정','evidence':'주거 변화',
            'source_ids':['L1'],'verification_status':'context_corroborated',
            'evidence_role':'surrounding_context','change_state':'scheduled'}]}
        lens=audience_lenses(full_profile('resident_population'),ctx)[-1]
        self.assertEqual(lens['axis'],'local_context')
        self.assertIn('예정',lens['observation'])
        self.assertIn('점포 수요 영향 미확인',lens['observation'])
        self.assertEqual(lens['context_source_refs'],[{'module':'local','source_id':'L1'}])
        ctx['local_signals'][0]['verification_status']='candidate'
        self.assertFalse(any(l['axis']=='local_context' for l in audience_lenses(full_profile('resident_population'),ctx)))

    def test_article_mechanism_overrides_search_mechanism_in_transfer(self):
        case={'source_ids':['T1'],'taxonomy_tags':['game_interaction'],'case_detail':{
            'status':'text_corroborated','source_ids':['T1'],
            'reported_mechanisms':[{'mechanism':'photo_sharing','source_ids':['T1']}]}}
        fit=audience_fit_questions(case,{'population_signals':[full_profile()]})[0]
        self.assertIn('촬영 결과물',fit['next_check'])
        self.assertNotIn('조작 과제',fit['next_check'])
        self.assertEqual(fit['mechanism_basis'],'article_keyword_check')

    def test_context_contrasts_change_questions_and_labels_alone_do_not(self):
        request,ctx,cache=inputs()
        contrasts=evaluate_context_contrasts(request,ctx,cache)
        self.assertEqual(len(contrasts),5)
        self.assertTrue(all(c['changed_fit_question_count']==3 for c in contrasts))
        self.assertTrue(all(c['selection_overlap']==1 for c in contrasts))
        a,_=replay(request,profile(ctx,'20s','male'),cache)
        b,_=replay(request,profile(ctx,'60_plus','female'),cache)
        self.assertEqual(compare(a,b)['changed_adaptation_count'],0)
        # Merely editing the displayed observed ratio must not pass evaluation.
        changed=deepcopy(a)
        fit=changed['reference_cases'][0]['audience_fit'][0]
        old=fit['question_basis'][0]['observation']
        fit['question_basis'][0]['observation']='표기만 바꿈'
        fit['rationale']=fit['rationale'].replace(old,'표기만 바꿈')
        self.assertEqual(compare(a,changed)['changed_fit_question_count'],0)

    def test_brief_and_research_review_keep_design_without_duplicate_diagnostics(self):
        request,ctx,cache=inputs(); bundle=evidence(); bundle['request']=request
        ctx['population_signals']=[full_profile(k) for k in
            ('floating_population','sales','resident_population','worker_population')]
        new,_=replay(request,ctx,cache)
        bundle['results']['trend']=new; bundle['module_status']['trend']=new['status']
        brief=generate_brief(bundle)
        cards=[c for c in brief['trend_patterns'] if c.get('type')=='reference_case']
        self.assertTrue(all(len(c['audience_fit'])==4 for c in cards))
        payload=build_research_input(bundle,run_critic(bundle))
        self.assertTrue(all('question_basis' not in f for c in payload['cases'] for f in c['audience_fit']))
        self.assertIn('여러 사용 장면',payload['cases'][0]['audience_fit'][0]['next_check'])
        self.assertIn('question_basis',cards[0]['audience_fit'][0])
        self.assertLess(len(json.dumps(payload,ensure_ascii=False).encode()),60000)


if __name__=='__main__': unittest.main()
