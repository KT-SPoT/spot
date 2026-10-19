import copy
import unittest

from src.brief.experience_connections import connections, reported_actions
from src.brief.regional_insights import regional_insights


def card(population, shares):
    return {'module':'quant', 'population_kind':population, 'title':population+' 연령 구성',
            'shares':{k:{'share_pct':v} for k,v in shares.items()}, 'reference_period':'2026-07',
            'scope':'선택 영역', 'sources':[{'source_id':'S-Q-001'}]}


class ExperienceConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.case={'event_name':'촬영 팝업', 'observation':'촬영 결과를 SNS로 공유한다.',
                   'sources':[{'source_id':'S-T-001'}],
                   'adaptation_hypotheses':[{'mechanism':'photo_sharing'}]}

    def test_same_case_changes_with_separate_population_observations(self):
        dongnae=[card('sales', {'60_plus':58.3,'20s':6}), card('floating_population',{'60_plus':37,'20s':9})]
        seoul=[card('sales', {'20s':36.1,'60_plus':7.3}), card('floating_population',{'60_plus':24,'20s':13})]
        before=copy.deepcopy(self.case)
        a=connections(self.case,dongnae);b=connections(self.case,seoul)
        self.assertEqual(a,[])
        self.assertEqual(b,[])
        self.assertIn('60대 이상 58.3%',regional_insights(dongnae)[0]['observation'])
        self.assertIn('20대 36.1%',regional_insights(seoul)[0]['observation'])
        self.assertEqual(self.case,before)

    def test_worker_scene_does_not_create_joint_age_worker_cohort(self):
        quant=[card('sales',{'20s':60}), {'title':'직장인구','value':1000,'reference_period':'2026년 상반기',
                                       'sources':[{'source_id':'S-Q-002'}]}]
        rows=connections(self.case,quant)
        self.assertEqual(rows,[])
        self.assertNotIn('20대 직장인 고객',' '.join(r['statement'] for r in rows))

    def test_missing_action_is_reference_only_and_missing_observation_has_no_link(self):
        self.assertEqual(connections(self.case,[]),[])
        for text in ('축제 체험 및 부대행사를 운영한다.','새 상품을 전시한다.',''):
            case={**self.case,'observation':text}
            self.assertEqual(reported_actions(case),[])
            self.assertEqual(connections(case,[card('sales',{'20s':60})]),[])
        self.assertEqual(reported_actions({**self.case,'sources':[]}),[])
        c=card('sales',{'20s':float('nan'),'60_plus':0})
        self.assertEqual(connections(self.case,[c]),[])
        c=card('sales',{'20s':50,'60_plus':50})
        self.assertEqual(connections(self.case,[c]),[])

    def test_promoter_is_not_relabelled_visitor(self):
        case={**self.case,'event_name':'축제 홍보대사 위촉','observation':'유튜브 영상 촬영과 개인 SNS를 활용해 현장을 소개한다.'}
        self.assertIn('홍보자가',reported_actions(case)[0][1])
        self.assertNotIn('방문객',str(connections(case,[card('sales',{'20s':60})])))

    def test_direct_trial_needs_more_than_category_or_word_experience(self):
        case={**self.case,'adaptation_hypotheses':[{'mechanism':'direct_product_trial'}]}
        self.assertEqual(reported_actions({**case,'observation':'체험행사를 운영한다.'}),[])
        self.assertEqual(reported_actions({**case,'observation':'현장에서 게임을 체험하고 비교한다.'})[0][0],'direct_product_trial')

    def test_mission_action_does_not_require_response_data(self):
        case={**self.case,'adaptation_hypotheses':[{'mechanism':'mission_journey'}],
              'observation':'참여자가 미션을 수행하고 완료 결과를 확인한다.'}
        timing={'module':'quant','population_kind':'sales','distribution_kind':'time','shares':{'18_23':{'share_pct':48}},'sources':[{'source_id':'S-Q-time'}]}
        row=connections(case,[card('sales',{'20s':60}),timing])[0]
        self.assertEqual(row['mechanism'],'mission_journey')
        self.assertIn('18~23시 48%',row['statement'])
        self.assertEqual(row['context_source_refs'],[{'module':'quant','source_id':'S-Q-time'}])
        self.assertEqual(reported_actions({**case,'observation':'미션 체험행사 예정'}),[])

    def test_reported_visitor_trial_accepts_news_wording(self):
        case={**self.case,'adaptation_hypotheses':[],
              'taxonomy_tags':['direct_product_trial']}
        for text in ('한자리에서 상품을 직접 보고 체험할 수 있었다.',
                     '방문객은 온라인에서만 보던 제품을 직접 경험할 수 있어 좋았다고 말했다.'):
            self.assertEqual(reported_actions({**case,'observation':text})[0][0],
                             'direct_product_trial')

    def test_trial_recommendation_is_not_a_reported_action(self):
        case={**self.case,'taxonomy_tags':['direct_product_trial'],
              'adaptation_hypotheses':[]}
        for text in ('제품을 직접 체험하는 행사를 운영해야 함.',
                     '소비자가 직접 발라보고 비교할 수 있는 접점을 넓혀야 한다.'):
            self.assertEqual(reported_actions({**case,'observation':text}),[])
        mixed='직접 체험을 권장한다. 현장에서는 방문객이 제품을 직접 보고 체험했다.'
        self.assertEqual(reported_actions({**case,'observation':mixed})[0][0],
                         'direct_product_trial')


if __name__=='__main__':unittest.main()
