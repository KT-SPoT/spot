"""Adapter/graph behavior, not an assertion of a real model's judgment accuracy."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import httpx

from src.critic.critic import run_critic
from src.critic.semantic import build_input, validate_response, run_semantic, ChatCaller, SemanticError, PROMPT
from src.graph.graph import build_graph

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'samples/critic/research_bundle.synthetic.json').read_text())


def answer(payload):
    return {'findings': [{'claim_id': c['claim_id'], 'verdict': 'insufficient',
        'source_ids': [], 'reason': '제공된 자료만으로 판단이 어렵습니다.', 'suggested_action': 'manual_check'}
        for c in payload['claims']]}


class SemanticCriticTests(unittest.TestCase):
    def setUp(self):
        profile = patch.dict(os.environ, {'SPOT_CRITIC_PROFILE': 'evidence'})
        profile.start()
        self.addCleanup(profile.stop)
        self.env = patch.dict(os.environ, {'SPOT_SEMANTIC_MODE': 'off', 'SPOT_SCOUT_MODE': 'live',
                                           'SPOT_LLM_MODEL': '', 'SPOT_LLM_ENDPOINT': '', 'LLM_API_KEY': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bundle = copy.deepcopy(BASE)
        self.critic = run_critic(self.bundle)
        self.payload = build_input(self.bundle, self.critic)

    def run_review(self, caller, **kwargs):
        return run_semantic(self.bundle, self.critic, caller=caller, mode='shadow', **kwargs)

    def test_default_disabled_and_missing_configuration_do_not_call(self):
        caller = Mock()
        self.assertEqual(run_semantic(self.bundle, self.critic, caller=caller)['code'], 'DISABLED')
        caller.assert_not_called()
        self.assertEqual(self.run_review(None)['code'], 'INVALID_CONFIGURATION')
        with patch.dict(os.environ, {'SPOT_SCOUT_MODE': 'offline'}):
            self.assertEqual(self.run_review(caller)['code'], 'DISABLED')
        caller.assert_not_called()

    def test_success_records_findings_without_truth_approval_or_mutation(self):
        before = copy.deepcopy(self.bundle)
        caller = Mock(side_effect=answer)
        result = self.run_review(caller)
        self.assertTrue(result['performed'])
        self.assertEqual(result['status'], 'manual_review')
        self.assertFalse(result['truth_verified'])
        self.assertEqual(result['call_count'], 1)
        caller.assert_called_once()
        self.assertEqual(self.bundle, before)

    def test_invalid_partial_duplicate_or_invented_responses_rejected(self):
        raw = answer(self.payload)
        bad = [[], {'findings': []}, {'findings': raw['findings'] + [raw['findings'][0]]}]
        for field, value in [('claim_id', 'invented'), ('source_ids', ['invented']),
                             ('verdict', 'pass'), ('reason', ''), ('suggested_action', 'search')]:
            changed = copy.deepcopy(raw)
            changed['findings'][0][field] = value
            bad.append(changed)
        for response in bad:
            with self.subTest(response=response), self.assertRaises((SemanticError, ValueError)):
                validate_response(response, self.payload)
        self.assertFalse(self.run_review(lambda p: 'invalid JSON')['performed'])

    def test_sources_must_belong_to_claim_and_support_needs_reference(self):
        for refs in ([], ['S-T-001']):
            raw = answer(self.payload)
            raw['findings'][0].update(verdict='supported', suggested_action='keep', source_ids=refs)
            with self.assertRaises(SemanticError):
                validate_response(raw, self.payload)

    def test_policy_derives_known_actions_without_changing_model_judgment(self):
        raw = answer(self.payload)
        raw['findings'][0]['suggested_action'] = 'qualify'
        before = copy.deepcopy(raw)
        adjustments = []
        findings = validate_response(raw, self.payload, action_normalizations=adjustments)
        self.assertEqual(findings[0]['verdict'], 'insufficient')
        self.assertEqual(findings[0]['reason'], before['findings'][0]['reason'])
        self.assertEqual(findings[0]['suggested_action'], 'manual_check')
        self.assertEqual(raw, before)
        self.assertEqual(adjustments, [{'claim_id': raw['findings'][0]['claim_id'],
            'model_action': 'qualify', 'applied_action': 'manual_check'}])
        result = self.run_review(lambda payload: raw)
        self.assertTrue(result['performed'])
        self.assertEqual(result['status'], 'manual_review')
        self.assertEqual(len(result['action_normalizations']), 1)

    def test_policy_cannot_normalize_an_unknown_action_or_invalid_reference(self):
        for field, value in [('suggested_action', 'execute_search'), ('source_ids', ['invented-source'])]:
            raw = answer(self.payload)
            raw['findings'][0]['suggested_action'] = 'qualify'
            raw['findings'][0][field] = value
            adjustments = []
            with self.assertRaises(SemanticError):
                validate_response(raw, self.payload, action_normalizations=adjustments)
            self.assertEqual(adjustments, [])

    def test_excluded_module_and_sensitive_material_not_sent(self):
        self.critic['checks']['excluded_modules'] = ['local']
        secret = 'synthetic-secret-value-for-redaction'
        self.bundle['request']['store']['name'] = secret + ' https://example.invalid/?certKey=hidden'
        self.bundle['results']['quant']['raw_html'] = '<html>PRIVATE</html>'
        with patch.dict(os.environ, {'LLM_API_KEY': secret}):
            payload = build_input(self.bundle, self.critic)
        encoded = json.dumps(payload)
        self.assertNotIn(secret, encoded)
        self.assertNotIn('certKey', encoded)
        self.assertNotIn('PRIVATE', encoded)
        self.assertFalse(any(c['claim_id'].startswith('local:') for c in payload['claims']))
        self.assertTrue(any(c['claim_id'].startswith('trend:pattern:') for c in payload['claims']))

    def test_search_snippet_marked_and_merged_excerpt_not_copied_to_all_sources(self):
        local = self.bundle['results']['local']
        local['insights'][0].update(evidence_basis='search_passage', source_ids=['S-L-001', 'S-L-002'])
        second = copy.deepcopy(local['sources'][0]); second['source_id'] = 'S-L-002'
        local['sources'].append(second)
        payload = build_input(self.bundle, self.critic)
        claim = next(c for c in payload['claims'] if c['claim_id'].startswith('local:'))
        self.assertEqual(claim['evidence'][0]['kind'], 'search_snippet')
        self.assertIsNone(claim['evidence'][0]['truncated'])
        self.assertIsNone(claim['evidence'][1]['text'])

    def test_limits_prevent_call_and_response_acceptance(self):
        caller = Mock(side_effect=answer)
        with patch('src.critic.semantic.MAX_INPUT_BYTES', 10):
            self.assertEqual(self.run_review(caller)['code'], 'INPUT_LIMIT_EXCEEDED')
        caller.assert_not_called()
        with patch('src.critic.semantic.MAX_OUTPUT_BYTES', 10):
            self.assertEqual(self.run_review(caller)['code'], 'OUTPUT_LIMIT_EXCEEDED')

    def test_no_usable_claims_do_not_call(self):
        self.critic['checks']['excluded_modules'] = ['quant', 'local', 'trend']
        caller = Mock()
        self.assertEqual(self.run_review(caller)['code'], 'NO_USABLE_CLAIMS')
        caller.assert_not_called()

    def test_quant_verified_cards_preserve_population_and_unknown_period_without_archive(self):
        card = {'module': 'quant', 'population_kind': 'resident_population',
                'reference_period': None, 'shares': {'female': {'share_pct': 51}},
                'sources': [{'source_id': 'S-Q-001', 'source_url': 'https://example.invalid/?certKey=PRIVATE'}]}
        with patch('src.critic.semantic.generate_brief', return_value={'unique_local_signals': [card]}):
            payload = build_input(self.bundle, self.critic, quant_evidence={'reports': {'html': 'RAW_ARCHIVE'}})
        self.assertEqual(payload['quant_facts'][0]['population_kind'], 'resident_population')
        self.assertIsNone(payload['quant_facts'][0]['reference_period'])
        self.assertNotIn('RAW_ARCHIVE', json.dumps(payload))
        self.assertNotIn('PRIVATE', json.dumps(payload))

    def test_quant_metric_refs_resolve_only_through_matching_verified_cards(self):
        quant = self.bundle['results']['quant']
        quant['insights'][0]['metric_refs'] = ['resident_population', 'unknown_metric']
        quant['insights'][0].pop('source_ids', None)
        card = {'module': 'quant', 'metric_refs': ['resident_population'], 'reference_period': None,
                'statement': 'SYNTHETIC 주거인구 100명', 'sources': [{'source_id': 'S-Q-001'}]}
        other = {'module': 'quant', 'metric_refs': ['unrelated_metric'],
                 'statement': 'UNRELATED', 'sources': [{'source_id': 'S-Q-001'}]}
        foreign = {'module': 'quant', 'metric_refs': ['resident_population'],
                   'statement': 'FOREIGN', 'sources': [{'source_id': 'not_in_quant_registry'}]}
        with patch('src.critic.semantic.generate_brief', return_value={'unique_local_signals': [card, other, foreign]}):
            payload = build_input(self.bundle, self.critic)
        claim = next(c for c in payload['claims'] if c['claim_id'].startswith('quant:'))
        self.assertEqual([e['source_id'] for e in claim['evidence']], ['S-Q-001'])
        self.assertEqual(claim['evidence'][0]['kind'], 'verified_metric')
        self.assertEqual(claim['evidence'][0]['text'], card['statement'])
        self.assertIsNone(claim['evidence'][0]['metric_facts'][0]['reference_period'])
        self.assertEqual(claim['unverified_metric_refs'], ['unknown_metric'])
        raw = answer(payload)
        raw['findings'][0].update(verdict='supported', suggested_action='keep', source_ids=['S-Q-001'])
        self.assertEqual(validate_response(raw, payload)[0]['verdict'], 'supported')

    def test_quant_unmatched_metric_does_not_borrow_other_card_source(self):
        quant = self.bundle['results']['quant']
        quant['insights'][0]['metric_refs'] = ['missing_metric']
        quant['insights'][0].pop('source_ids', None)
        card = {'module': 'quant', 'metric_refs': ['other_metric'], 'statement': 'SYNTHETIC 다른 수치',
                'sources': [{'source_id': 'S-Q-001'}]}
        with patch('src.critic.semantic.generate_brief', return_value={'unique_local_signals': [card]}):
            payload = build_input(self.bundle, self.critic)
        claim = next(c for c in payload['claims'] if c['claim_id'].startswith('quant:'))
        self.assertEqual(claim['evidence'], [])
        self.assertEqual(claim['unverified_metric_refs'], ['missing_metric'])

    def test_provider_exception_text_is_never_returned(self):
        for error, code in [(httpx.ReadTimeout('PRIVATE'), 'PROVIDER_TIMEOUT'),
                            (RuntimeError('PRIVATE'), 'EVALUATION_FAILED')]:
            caller = Mock(side_effect=error)
            result = self.run_review(caller)
            self.assertEqual(result['code'], code)
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertEqual(result['call_count'], 1)

    def test_http_adapter_single_request_and_json_validation(self):
        captured = []
        def handle(request):
            captured.append(request)
            body = json.loads(request.content)
            self.assertEqual(body['response_format'], {'type': 'json_object'})
            payload = json.loads(body['messages'][1]['content'])
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(answer(payload))}}]})
        caller = ChatCaller('https://example.invalid/v1/chat/completions', 'test-model', 'test-key',
                            transport=httpx.MockTransport(handle))
        self.assertTrue(self.run_review(caller)['performed'])
        self.assertEqual(len(captured), 1)

    def test_http_quota_auth_redirect_refusal_and_size_never_retry(self):
        responses = [httpx.Response(s, text='PRIVATE') for s in (401, 429, 503, 302)]
        responses += [httpx.Response(200, json={'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}),
                      httpx.Response(200, text='x' * 64001)]
        for response in responses:
            calls = []
            def handle(request):
                calls.append(request)
                return response
            caller = ChatCaller('https://example.invalid/v1/chat/completions', 'test', 'test',
                                transport=httpx.MockTransport(handle))
            self.assertFalse(self.run_review(caller)['performed'])
            self.assertEqual(len(calls), 1)

    def test_endpoint_rejects_credentials_and_insecure_urls(self):
        for url in ('http://example.invalid', 'https://u:p@example.invalid',
                    'https://example.invalid?key=x', 'https://example.invalid#key=x'):
            with self.assertRaises(SemanticError):
                ChatCaller(url, 'test', 'test')

    def test_nine_synthetic_examples_validate_expected_response_only(self):
        # This verifies fixtures/response shape, NOT model semantic accuracy.
        cases = json.loads((ROOT / 'samples/critic/semantic_cases.synthetic.json').read_text())['cases']
        self.assertEqual(len(cases), 9)
        for case in cases:
            payload = {'claims': [{'claim_id': case['case_id'], 'evidence': case['evidence']}]}
            raw = {'findings': [{'claim_id': case['case_id'], **case['expected']}]}
            self.assertEqual(validate_response(raw, payload)[0]['verdict'], case['expected']['verdict'])

    def test_graph_evaluates_once_after_scout_retry_and_keeps_brief(self):
        bad = copy.deepcopy(BASE['results']['local'])
        bad.update(status='failed', insights=[], sources=[], errors=[{'code': 'PROVIDER_UNAVAILABLE'}])
        def execute(caller, mode):
            with patch('src.graph.graph.run_quant_scout', return_value=BASE['results']['quant']), \
                 patch('src.graph.graph.run_local_scout', side_effect=[bad, BASE['results']['local']]), \
                 patch('src.graph.graph.run_trend_scout', return_value=BASE['results']['trend']):
                return build_graph(semantic_caller=caller, semantic_mode=mode).invoke({'request': BASE['request']})
        off = execute(None, 'off')
        caller = Mock(side_effect=answer)
        on = execute(caller, 'shadow')
        caller.assert_called_once()
        self.assertEqual(on['retry_count'], 1)
        self.assertTrue(on['critic_result']['checks']['semantic_review']['performed'])
        self.assertEqual(off['research_brief'], on['research_brief'])
        failed = execute(Mock(side_effect=RuntimeError('PRIVATE')), 'shadow')
        self.assertEqual(off['research_brief'], failed['research_brief'])

    def test_three_area_requests_pass_their_own_scope_through_graph(self):
        # End-to-end wiring with synthetic Scouts/evaluator, not real model accuracy.
        profiles = json.loads((ROOT / 'samples/critic/area_profiles.synthetic.json').read_text())['profiles']
        self.assertEqual(len(profiles), 3)
        for profile in profiles:
            with self.subTest(profile=profile['profile_id']):
                bundle = copy.deepcopy(BASE)
                request = bundle['request']
                request['store'] = profile['store']
                request['research'].update(radius_m=profile['radius_m'], comparison_area=profile['comparison_area'])
                local = bundle['results']['local']
                local['query_context'].update(area_anchor=profile['area_anchor'], scope='SYNTHETIC: 점포 반경 미검증')
                local['insights'][0].update(title='SYNTHETIC 가상 시설 계획',
                    evidence='SYNTHETIC: 인접생활권 A의 가상 시설 도입 계획. 요청 점포와의 거리는 미확보.',
                    evidence_role='surrounding_context', locality_tags=['SYNTHETIC 인접생활권 A'],
                    context_note='요청 지역 내부 사업인지 미확인', evidence_basis='article_text')
                quant = bundle['results']['quant']
                quant['query_context'].update(lat=None, lng=None, radius_m=profile['radius_m'])
                trend = bundle['results']['trend']
                trend['query_context']['scope'] = 'SYNTHETIC: 타 지역 체험 참고 후보'
                captured = []
                def evaluate(payload):
                    captured.append(copy.deepcopy(payload))
                    return answer(payload)
                with patch('src.graph.graph.run_quant_scout', return_value=quant), \
                     patch('src.graph.graph.run_local_scout', return_value=local), \
                     patch('src.graph.graph.run_trend_scout', return_value=trend):
                    state = build_graph(semantic_caller=evaluate, semantic_mode='shadow').invoke({'request': request})
                self.assertEqual(len(captured), 1)
                payload = captured[0]
                self.assertEqual(payload['request']['store'], profile['store'])
                self.assertEqual(payload['request']['research']['radius_m'], profile['radius_m'])
                self.assertEqual(payload['request']['research']['comparison_area'], profile['comparison_area'])
                self.assertEqual(payload['scout_scopes']['local']['area_anchor'], profile['area_anchor'])
                self.assertIsNone(payload['scout_scopes']['quant']['lat'])
                local_claim = next(c for c in payload['claims'] if c['claim_id'].startswith('local:'))
                self.assertEqual(local_claim['content']['evidence_role'], 'surrounding_context')
                self.assertEqual(state['critic_result']['status'], 'manual_review')
                self.assertEqual(state['research_bundle']['request']['store'], profile['store'])
                self.assertFalse(state['critic_result']['checks']['semantic_review']['truth_verified'])

    def test_prompt_has_no_fixed_neighborhood_and_missing_scope_stays_unknown(self):
        self.assertNotIn('Myeongji', PROMPT)
        self.assertNotIn('Eco Delta', PROMPT)
        self.bundle['request']['store'] = {'name': 'SYNTHETIC 미확정 점포', 'address': None}
        payload = build_input(self.bundle, self.critic)
        self.assertIsNone(payload['request']['store']['address'])
        self.assertIsNone(payload['request']['store']['lat'])
        self.assertIsNone(payload['scout_scopes']['local']['area_anchor'])

    def test_source_location_and_resolution_metadata_are_preserved_without_private_fields(self):
        quant = self.bundle['results']['quant']
        quant['query_context'].update(lat=35.1, lng=129.1, resolved_address='SYNTHETIC 확정 주소',
            coordinate_source='synthetic_geocoder', verification_log=[{'private': 'DO_NOT_SEND'}])
        self.bundle['results']['trend']['insights'][0].update(location='SYNTHETIC 다른 생활권', brand='SYNTHETIC 브랜드')
        payload = build_input(self.bundle, self.critic)
        self.assertEqual(payload['scout_scopes']['quant']['lat'], 35.1)
        self.assertEqual(payload['scout_scopes']['quant']['resolved_address'], 'SYNTHETIC 확정 주소')
        self.assertNotIn('DO_NOT_SEND', json.dumps(payload))
        trend = next(c for c in payload['claims'] if c['claim_id'].startswith('trend:insight:'))
        self.assertEqual(trend['content']['location'], 'SYNTHETIC 다른 생활권')


if __name__ == '__main__':
    unittest.main()
