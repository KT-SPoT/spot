"""Audience interventions must detect label-only behavior, not invent preference."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from src.evaluation.trend_audience import compare, evaluate, profile, projection, replay
from src.graph.trend_context import build_trend_context
from src.scouts.trend import build_queries
from tests.test_trend_context import evidence
from tests.test_local import article


def inputs():
    bundle=evidence()
    request=bundle['request']
    request['research']['reference_date']='2026-10-01'
    context=build_trend_context(request,bundle['results']['quant'],bundle['results']['local'])
    rows=[article('서울 게임 별빛 팝업 미니게임 체험','https://example.org/game'),
          article('대구 음식 달빛 팝업 시식 체험','https://example.org/food'),
          article('제주 솔바람 축제 스탬프 미션 체험','https://example.org/festival')]
    return request,context,{query:deepcopy(rows) for query in build_queries(request,context)}


class AudienceEvaluationTests(unittest.TestCase):
    def test_label_only_changes_are_detected_as_partial_not_success(self):
        request,context,cache=inputs()
        summary,outputs=evaluate(request,context,cache)
        self.assertEqual(summary['profile_count'],6)
        self.assertEqual(summary['verdict'],'partial_audience_conditioning')
        self.assertEqual(summary['selection_changes'],0)
        self.assertEqual(summary['adaptation_changes'],0)
        self.assertEqual(summary['fit_question_changes'],0)
        self.assertTrue(all(c['changed_audience_label_count']==3 for c in summary['comparisons']))
        self.assertTrue(summary['repeatable'])
        self.assertTrue(summary['missing_profile_has_no_fit'])
        self.assertTrue(summary['mixed_population_kept_separate'])

    def test_matching_metadata_changes_score_without_industry_stereotypes(self):
        request,context,cache=inputs()
        for rows in cache.values():
            rows[0]['title']='서울 게임 별빛 팝업 20대 남성 미니게임 체험'
            rows[1]['title']='대구 음식 달빛 팝업 60대 여성 시식 체험'
        young,_=replay(request,profile(context,'20s','male'),cache)
        older,_=replay(request,profile(context,'60_plus','female'),cache)
        compared=compare(young,older)
        self.assertEqual(compared['changed_score_count'],2)
        self.assertEqual({c['event_category'] for c in older['reference_cases']},{'game','food','festival'})
        self.assertFalse(any(c.get('proven_preference') for c in older['reference_cases']))

    def test_replay_is_immutable_and_never_reads_articles_or_video(self):
        request,context,cache=inputs();before=deepcopy([request,context,cache])
        with patch('src.scouts.search_runtime.get_json',side_effect=AssertionError('network')):
            result,_=replay(request,context,cache)
        self.assertEqual(before,[request,context,cache])
        self.assertEqual(len(result['reference_cases']),3)

    def test_missing_query_fails_instead_of_searching_live(self):
        request,context,cache=inputs();cache.pop(next(iter(cache)))
        with self.assertRaises(ValueError):replay(request,context,cache)

    def test_no_references_is_inconclusive_not_personalization_failure(self):
        request,context,cache=inputs()
        summary,_=evaluate(request,context,{query:[] for query in cache})
        self.assertEqual(summary['verdict'],'insufficient_reference_evidence')
        self.assertIsNone(summary['comparisons'][0]['selection_overlap'])

    def test_article_source_ids_are_rebound_when_order_changes(self):
        request,context,cache=inputs()
        details={'https://example.org/game':{'status':'text_corroborated',
                 'source_ids':['OLD-ID'],'reported_mechanisms':[{'mechanism':'game_interaction','source_ids':['OLD-ID']}],
                 'response_signals':[],'event_verified':False,'demographic_response_established':False}}
        result,_=replay(request,profile(context,'20s','male'),cache,details)
        case=next(c for c in result['reference_cases'] if c['event_category']=='game')
        self.assertEqual(case['case_detail']['source_ids'],case['source_ids'])
        self.assertEqual(case['audience_fit'][0]['mechanism_source_ids'],case['source_ids'])
        self.assertEqual(details['https://example.org/game']['source_ids'],['OLD-ID'])

    def test_question_comparison_is_only_on_common_cases(self):
        request,context,cache=inputs()
        result,_=replay(request,profile(context,'20s','male'),cache)
        changed=deepcopy(result)
        changed['reference_cases'][0]['audience_fit'][0]['next_check']='다른 검토 질문'
        self.assertEqual(compare(result,changed)['changed_fit_question_count'],1)
        changed['reference_cases']=changed['reference_cases'][1:]
        self.assertEqual(compare(result,changed)['changed_fit_question_count'],0)
        self.assertLess(compare(result,changed)['selection_overlap'],1)


if __name__=='__main__':unittest.main()
