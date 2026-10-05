import copy
import unittest

from src.brief.experience_connections import connections, reported_actions


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
        self.assertIn('60대 이상 58.3%',a[0]['statement'])
        self.assertIn('20대 36.1%',b[0]['statement'])
        self.assertIn('서로 다른 후보',b[1]['statement'])
        self.assertNotIn('서로 다른 후보',' '.join(r['statement'] for r in a))
        self.assertEqual(self.case,before)
        self.assertEqual(b[0]['context_source_refs'],[{'module':'quant','source_id':'S-Q-001'}])
        self.assertIn('상품 선호가 아님',b[0]['statement'])

    def test_worker_scene_does_not_create_joint_age_worker_cohort(self):
        quant=[card('sales',{'20s':60}), {'title':'직장인구','value':1000,'reference_period':'2026년 상반기',
                                       'sources':[{'source_id':'S-Q-002'}]}]
        rows=connections(self.case,quant)
        self.assertIn('업무 중 사용하는 기능',rows[1]['statement'])
        self.assertIn('매출 연령대와 합쳐',rows[1]['statement'])
        self.assertNotIn('20대 직장인 고객',' '.join(r['statement'] for r in rows))
        self.assertIn('S-Q-002',str(rows[1]['context_source_refs']))

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
        self.assertEqual(connections(case,[card('sales',{'20s':60})])[0]['mechanism'],'mission_journey')
        self.assertEqual(reported_actions({**case,'observation':'미션 체험행사 예정'}),[])


if __name__=='__main__':unittest.main()
