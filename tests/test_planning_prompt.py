import copy
import unittest
from src.brief.planning_prompt import render_support
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
        result=render_support(brief,request)
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
        result=render_support({'local_changes':[{'title':'연결점이 약한 기사','evidence':'역사를 소개한다.',
            'sources':[{'source_url':'https://user:password@news.example/a'},{'source_url':'javascript:alert(1)'}]}]}, {})
        self.assertIn('정량 자료 미확보',result)
        self.assertIn('미정 — 사용자가 기획 단계에서 선택',result)
        self.assertIn('연결점이 약한 기사',result)
        self.assertIn('예산·인력·공간·기간',result)
        self.assertNotIn('password',result)
        self.assertNotIn('javascript:',result)
        self.assertIn('[조사자료 끝]',result)

    def test_hints_follow_six_fields_without_generating_final_prompt(self):
        text=render_handoff({}, {'store':{'name':'새 매장'}})
        self.assertGreater(len(text.strip().splitlines()),6)
        labels=['1. 상권','2. 타깃 고객','3. 타깃 상품','4. 행사 기간','5. 직원 수','6. 판촉물 예산']
        self.assertEqual(sorted(text.index(label) for label in labels),[text.index(label) for label in labels])
        self.assertIn('3. 타깃 상품\n\n',text)
        self.assertIn('5. 직원 수\n\n',text)
        self.assertNotIn('기획해주세요',text)
        self.assertNotIn('실행안을 작성',text)
        self.assertNotIn('근거:',text)
        self.assertNotIn('조사에서 발견한',text)

    def test_user_conditions_and_promo_candidate_do_not_become_observed_inventory(self):
        brief={'trend_patterns':[{'type':'reference_case','observation':'현장 체험을 촬영해 SNS로 공유한다.',
                                 'sources':[{'source_url':'https://example.org/event'}],
                                 'adaptation_hypotheses':[{'mechanism':'photo_sharing'}]}]}
        text=render_handoff(brief,{}, {'event_period':'11월 2일, 준비 포함 4시간','staff':'2명',
                                    'promotional_items':'휴대폰 거치대','budget':'10만원','target_product':'중저가 단말기'})
        self.assertNotIn('사진 결과물 카드',text)
        self.assertNotIn('2명',text)
        self.assertNotIn('10만원',text)
        self.assertNotIn('중저가 단말기',text)
        self.assertNotIn('4시간',text)

    def test_peak_time_is_not_event_duration_and_population_is_not_visitors(self):
        brief={'unique_local_signals':[
            {'module':'quant','title':'유동인구 시간별 비중','shares':{'14_18':{'share_pct':55}},'reference_period':'2026-08'},
            {'module':'quant','title':'주거인구','value':100},
            {'module':'quant','title':'직장인구','value':False}]}
        text=render_handoff(brief,{})
        self.assertIn('14~18시 55%',text)
        self.assertIn('시간대 비중',text)
        self.assertNotIn('숨은 기회 후보',text)
        self.assertNotIn('4시간 행사',text)

    def test_ideas_depend_on_observed_case_and_profile_not_generic_advice(self):
        brief={'unique_local_signals':[{'module':'quant','title':'유동인구 연령 구성','shares':{'20s':{'share_pct':35},'60_plus':{'share_pct':20}}}],
               'trend_patterns':[{'type':'reference_case','event_name':'촬영 팝업','observation':'20대가 촬영 결과를 SNS로 공유한다.',
                                  'sources':[{'source_url':'https://example.org/event'}],
                                  'adaptation_hypotheses':[{'mechanism':'photo_sharing'}]}]}
        text=render_handoff(brief,{})
        self.assertIn('20대 35%',text)
        self.assertIn('20대 언급 행사: ‘촬영 팝업’ — 촬영·결과물 공유',text)
        self.assertNotIn('선택하세요',text)
        self.assertNotIn('내가 정할 내용',text)
        brief['trend_patterns']=[]
        brief['unique_local_signals'][0]['shares']={'60_plus':{'share_pct':65}}
        changed=render_handoff(brief,{})
        self.assertIn('60대 이상 65%',changed)
        self.assertNotIn('20대 35%',changed)
        self.assertNotIn('사진 결과물 카드',changed)

    def test_sales_wins_over_population_and_unrelated_goods_stay_blank(self):
        from src.brief.planning_prompt import build_compact_clues
        brief={'unique_local_signals':[
            {'module':'quant','title':'유동인구 연령 구성','shares':{'60_plus':{'share_pct':60}}},
            {'module':'quant','title':'매출 연령 비중','shares':{'20s':{'share_pct':48}}},
            {'module':'quant','title':'매출 요일 비중','shares':{'sat':{'share_pct':24}}}],
            'trend_patterns':[{'type':'reference_case','event_name':'쿠키런 페스티벌',
                'observation':'게임 굿즈를 판매하고 기념품을 제공했다.',
                'sources':[{'source_url':'https://example.org/event'}],'taxonomy_tags':['collectible_reward']}]}
        model=build_compact_clues(brief,{})
        self.assertIn('매출액은 20대 48%',model['fields'][1]['summary'])
        self.assertIn('매출액 요일 비중',model['fields'][3]['summary'])
        self.assertEqual(model['fields'][5]['summary'],'')
        brief['trend_patterns'][0]['observation']='20대가 굿즈를 구매했다.'
        brief['trend_patterns'][0]['case_id']='T-1'
        brief['research_review']={'case_reviews':[{'case_id':'T-1','verdict':'generic'}]}
        self.assertEqual(build_compact_clues(brief,{})['fields'][5]['summary'],'')
        review=brief['research_review']['case_reviews'][0]
        review['dimensions']={'local_customer_fit':'weak','transfer_logic':'clear','differentiation':'generic','overclaim':'clear'}
        self.assertIn('20대 언급 행사',build_compact_clues(brief,{})['fields'][5]['summary'])
        review['dimensions']['overclaim']='risk'
        self.assertEqual(build_compact_clues(brief,{})['fields'][5]['summary'],'')
