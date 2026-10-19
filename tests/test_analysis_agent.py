import copy
import unittest
from src.brief.synthesis import run_synthesis, apply_synthesis, build_synthesis_input, candidate_schema, generation_input, resolve_analysis_draft
from src.brief.area_summary import area_summary
from tests.test_regional_synthesis import brief,answer,review

class AnalysisAgentTests(unittest.TestCase):
    def test_peak_day_is_not_weekend_total_and_input_is_preserved(self):
        p=build_synthesis_input(brief())
        p['observations'].append({'evidence_id':'day-check','module':'quant',
            'population_kind':'sales','distribution_kind':'day','observation':'요일 분포',
            'shares_pct':dict(zip(('mon','tue','wed','thu','fri','sat','sun'),
                (4,4,13.8,17.8,19,27.6,13.8)))})
        before=copy.deepcopy(p)
        written=generation_input(p)
        row=next(r for r in written['ingredient_groups']['consumption_timing'] if r['evidence_id']=='day-check')
        self.assertEqual(row['day_comparison']['peak_day'],'토요일')
        self.assertEqual(row['day_comparison']['weekday_total_pct'],58.6)
        self.assertEqual(row['day_comparison']['weekend_total_pct'],41.4)
        self.assertEqual(p,before)

    def test_rejected_area_does_not_promote_opportunity_into_summary(self):
        b=brief();old=b['overview']['area_summary']
        r=run_synthesis(b,caller=answer,reviewer=review)
        r['generated_candidates']=[{'insight_id':'area-reading'}]+r['insights']
        out=apply_synthesis(b,r)
        self.assertEqual(out['overview']['area_summary'],old)
        self.assertFalse(out['regional_synthesis']['area_summary_applied'])
        self.assertTrue(out['research_implications'])

    def test_writer_guidance_does_not_mutate_observations_or_add_quality_gate(self):
        payload=build_synthesis_input(brief());before=copy.deepcopy(payload)
        written=generation_input(payload)
        self.assertEqual(payload,before)
        self.assertIn('writing_plan',written)
        fields=candidate_schema(written)['properties']['area_reading']['properties']
        self.assertIn('3문장',written['writing_plan']['area_summary'])
        self.assertIn('지역의 성격',fields['regional_character']['description'])
        self.assertNotIn('maxLength',fields['regional_character'])
        for row in written['observations']:
            if row.get('distribution_kind') in ('age','gender'):
                self.assertIn('교차 집단',row['aggregation_note'])

    def test_region_and_five_evidence_slots(self):
        b=brief();b['_analysis_context']={'store':{'name':'동래점','address':'부산 동래구'},'research':{'radius_m':1000}}
        p=build_synthesis_input(b)
        self.assertEqual(p['region_context']['store']['address'],'부산 동래구')
        self.assertEqual(candidate_schema(p)['properties']['opportunities']['items']['properties']['evidence_ids']['maxItems'],5)
        self.assertEqual(candidate_schema(p)['properties']['area_reading']['properties']['place_evidence_ids']['minItems'],1)
        b['overview']['area_summary']='이전 AI의 주장'
        self.assertNotIn('이전 AI의 주장',str(build_synthesis_input(b)))

    def test_writer_selects_place_and_sales_pattern_separately(self):
        b=brief();b['unique_local_signals'].append({'module':'local','title':'시험역','type':'local_place','place':{'name':'시험역','category':'교통','distance_m':100},'evidence':'시험역 위치 정보','sources':[{'source_id':'L1','source_url':'https://public.example/place'}]})
        p=generation_input(build_synthesis_input(b));schema=candidate_schema(p)['properties']['area_reading']['properties']
        self.assertEqual(schema['place_evidence_ids']['items']['enum'],['E02'])
        self.assertEqual(schema['pattern_evidence_ids']['items']['enum'],['E00'])
        c=answer(p,links=False)['insights'][0]
        area={k:v for k,v in c.items() if k not in ('insight_id','evidence_ids','interpretation','planning_question')}
        area.update(regional_character='교통시설이 있는 지역입니다.',observed_connection='소비 요일에 맞춘 접점이 중요합니다.',promotion_opening='간단한 체험으로 참여 접점을 만듭니다.')
        area.update(place_evidence_ids=['E02'],pattern_evidence_ids=['E00'])
        resolved=resolve_analysis_draft({'area_reading':area,'opportunities':[]},p)
        self.assertEqual(resolved['insights'][0]['evidence_ids'],['E02','E00'])
        self.assertEqual(resolved['insights'][0]['interpretation'],'교통시설이 있는 지역입니다. 소비 요일에 맞춘 접점이 중요합니다. 간단한 체험으로 참여 접점을 만듭니다.')
        self.assertEqual(resolved['insights'][0]['planning_question'],area['promotion_opening'])
        area['place_evidence_ids']=['E00']
        from src.critic.semantic import SemanticError
        with self.assertRaises(SemanticError):resolve_analysis_draft({'area_reading':area,'opportunities':[]},p)

    def test_population_and_sales_ingredients_remain_separate(self):
        p=build_synthesis_input(brief())
        for index,(population,axis) in enumerate((('sales','age'),('sales','gender'),('worker_population','age'))):
            p['observations'].append({'evidence_id':f'X{index}','module':'quant','population_kind':population,'distribution_kind':axis,'shares_pct':{'20s':30},'observation':'표본 관측'})
        written=generation_input(p);groups=written['ingredient_groups']
        self.assertEqual([r['evidence_id'] for r in groups['sales_age_profile']],['X0'])
        self.assertEqual([r['evidence_id'] for r in groups['sales_gender_profile']],['X1'])
        self.assertIn('X2',[r['evidence_id'] for r in groups['population_context']])
        ids=[r['evidence_id'] for rows in groups.values() for r in rows]
        self.assertEqual(len(ids),len(set(ids)))

    def test_scope_correction_preserves_analysis_and_summary(self):
        def judge(p):
            r=review(p);c=copy.deepcopy(p['candidate_insights'][0])
            c['interpretation']='전국 체험 사례를 참고해 소비 요일에 맞춘 참여 접점을 만드는 것이 기회입니다.'
            r['reviews'][0].update(verdict='corrected_scope',corrected_insight=c)
            return r
        b=brief();result=run_synthesis(b,caller=answer,reviewer=judge)
        out=apply_synthesis(b,result)
        self.assertEqual(result['call_count'],2)
        self.assertEqual(area_summary(out),result['insights'][0]['interpretation'])
        self.assertTrue(out['trend_patterns'][0]['adaptation_hypotheses'])

    def test_mixed_city_removes_only_affected_candidate(self):
        def generate(p):
            r=answer(p);bad=copy.deepcopy(r['insights'][0]);bad['insight_id']='mixed';bad['interpretation']='다른 도시 시설을 지역 환경으로 잘못 연결한 문장'
            r['insights'].append(bad);return r
        def judge(p):
            r=review(p);r['reviews'][1]['verdict']='mixed_region';return r
        r=run_synthesis(brief(),caller=generate,reviewer=judge)
        self.assertEqual([x['insight_id'] for x in r['insights']],['I1'])
        self.assertEqual(len(apply_synthesis(brief(),r)['research_implications']),1)

    def test_correction_cannot_change_sources_or_invent_numbers(self):
        def judge(p):
            r=review(p);c=copy.deepcopy(p['candidate_insights'][0]);c['interpretation']='지역 매출 비중 99%'
            r['reviews'][0].update(verdict='corrected_scope',corrected_insight=c);return r
        r=run_synthesis(brief(),caller=answer,reviewer=judge)
        self.assertFalse(r['insights']);self.assertEqual(r['candidate_rejections'][0]['code'],'UNSUPPORTED_NUMERIC_CLAIM')

if __name__=='__main__':unittest.main()
