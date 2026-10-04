"""Research Critic contract, orchestration and graceful degradation, no paid calls."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from src.critic.research_review import build_research_input, validate_research_response, guard_suggestions, RESEARCH_PROMPT
from src.critic.semantic import run_semantic, SemanticError
from src.critic.critic import run_critic
from src.scouts.trend import run_trend_scout
from src.graph.trend_context import build_trend_context
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from tests.test_trend_context import evidence
from tests.test_local import article


def bundle():
    result = evidence()
    result['request']['research']['reference_date'] = '2026-10-01'
    context = build_trend_context(result['request'], result['results']['quant'])
    with patch('src.scouts.search_runtime.news', return_value=[article('제주 축제 미션 팝업 체험')]), \
         patch('src.scouts.search_runtime.videos', return_value=[]):
        result['results']['trend'] = run_trend_scout(result['request'], context=context)
    result['module_status']['trend'] = result['results']['trend']['status']
    return result


def answer(payload):
    return {'reviews': [{'case_id': c['case_id'], 'verdict': 'generic',
                        'dimensions': {'local_customer_fit': 'weak', 'transfer_logic': 'clear',
                                       'differentiation': 'generic', 'overclaim': 'clear'},
                        'reason': '참고 사례는 유용하지만 응용이 어느 매장에도 적용될 만큼 일반적입니다.',
                        'suggestion': '관측된 생활·통근 맥락에 연결할 기능 비교 질문을 구체화하세요.'}
                       for c in payload['cases']]}


class ResearchReviewTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'SPOT_CRITIC_PROFILE': 'research', 'SPOT_SCOUT_MODE': 'live'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.bundle = bundle(); self.critic = run_critic(self.bundle)
        self.payload = build_research_input(self.bundle, self.critic)

    def test_input_is_bounded_context_not_original_archives(self):
        self.assertEqual(len(self.payload['cases']), 1)
        self.assertTrue(self.payload['quant_observations'])
        encoded = json.dumps(self.payload, ensure_ascii=False)
        self.assertNotIn('source_url', encoded)
        self.assertNotIn('html', encoded)
        self.assertLess(len(encoded.encode()), 60000)

    def test_model_needs_no_source_ids_and_code_attaches_registered_refs(self):
        caller = Mock(side_effect=answer)
        before = copy.deepcopy(self.bundle)
        review = run_semantic(self.bundle, self.critic, caller=caller, mode='shadow')
        self.assertTrue(review['performed'])
        self.assertEqual(review['call_count'], 1)
        self.assertEqual(review['case_reviews'][0]['source_ids'], self.bundle['results']['trend']['insights'][0]['source_ids'])
        self.assertEqual(self.bundle, before)
        caller.assert_called_once()
        self.critic['checks']['semantic_review'] = review
        text = render_markdown(generate_brief(self.bundle, self.critic))
        self.assertIn('Critic: 고객 연결·차별성 검토', text)
        self.assertIn('어느 매장에도', text)
        self.assertFalse(review['truth_verified'])

    def test_incomplete_duplicate_unknown_and_extra_model_fields_rejected(self):
        base = answer(self.payload)
        bad = [{'reviews': []}, {'reviews': base['reviews'] * 2}]
        unknown = copy.deepcopy(base); unknown['reviews'][0]['case_id'] = 'unknown'; bad.append(unknown)
        extra = copy.deepcopy(base); extra['reviews'][0]['source_ids'] = ['invented']; bad.append(extra)
        for raw in bad:
            with self.assertRaises(SemanticError):
                validate_research_response(raw, self.payload)

    def test_useful_cannot_have_generic_or_risky_dimensions(self):
        raw = answer(self.payload); raw['reviews'][0]['verdict'] = 'useful'
        with self.assertRaises(SemanticError):
            validate_research_response(raw, self.payload)

    def test_failure_preserves_brief_and_does_not_trigger_scout_retry(self):
        caller = Mock(side_effect=RuntimeError('private-provider-value'))
        review = run_semantic(self.bundle, self.critic, caller=caller, mode='shadow')
        self.assertEqual(review['code'], 'EVALUATION_FAILED')
        self.critic['checks']['semantic_review'] = review
        brief = generate_brief(self.bundle, self.critic)
        self.assertTrue(brief['trend_patterns'])
        self.assertNotIn('private-provider-value', json.dumps(brief))
        self.assertEqual(review['call_count'], 1)
        self.assertEqual(self.critic['retry'], [])

    def test_disabled_offline_and_empty_cases_do_not_call(self):
        caller = Mock()
        with patch.dict('os.environ', {'SPOT_SCOUT_MODE': 'offline'}):
            self.assertEqual(run_semantic(self.bundle, self.critic, caller=caller, mode='shadow')['code'], 'DISABLED')
        self.critic['checks']['excluded_modules'] = ['trend']
        self.assertEqual(run_semantic(self.bundle, self.critic, caller=caller, mode='shadow')['code'], 'NO_USABLE_CASES')
        caller.assert_not_called()

    def test_another_area_is_passed_without_fixed_neighborhood(self):
        self.bundle['request']['store']['address'] = '서울특별시 마포구 합성 주소'
        payload = build_research_input(self.bundle, self.critic)
        self.assertIn('마포구', payload['request']['store']['address'])
        self.assertNotIn('명지', RESEARCH_PROMPT)
        self.assertIn('replacing the store/product name', RESEARCH_PROMPT)

    def test_unrecognized_adapter_error_cannot_echo_secrets(self):
        review = run_semantic(self.bundle, self.critic, mode='shadow', caller=Mock(side_effect=SemanticError('private-key-value')))
        self.assertEqual(review['code'], 'EVALUATION_FAILED')
        self.assertNotIn('private-key-value', json.dumps(review))

    def test_joint_cohort_suggestion_is_qualified_without_discarding_case(self):
        raw = answer(self.payload)
        raw['reviews'][0]['suggestion'] = '40대 남성 고객이 많은 시간대에 체험을 제공하세요.'
        rows = guard_suggestions(validate_research_response(raw, self.payload))
        self.assertNotIn('40대 남성', rows[0]['suggestion'])
        self.assertEqual(rows[0]['verdict'], 'generic')
        self.assertEqual(rows[0]['suggestion_basis'], 'policy_fallback')

    def test_joint_cohort_reason_is_guarded_but_explicit_warning_is_preserved(self):
        row = answer(self.payload)['reviews'][0]
        row['reason'] = '40대 남성 구매층이 많아 매장에 적합합니다.'
        guarded = guard_suggestions([row])[0]
        self.assertEqual(guarded['reason_basis'], 'policy_fallback')
        self.assertNotIn('40대 남성', guarded['reason'])
        reason = '40대 남성 고객이라고 단정할 수 없습니다.'
        row['reason'] = reason
        self.assertEqual(guard_suggestions([row])[0]['reason'], reason)

    def test_separate_distribution_suggestion_is_preserved(self):
        raw = answer(self.payload)
        suggestion = '주요 연령 40대와 주요 성별 남성의 각각의 분포를 참고하세요.'
        raw['reviews'][0]['suggestion'] = suggestion
        self.assertEqual(guard_suggestions(raw['reviews'])[0]['suggestion'], suggestion)
