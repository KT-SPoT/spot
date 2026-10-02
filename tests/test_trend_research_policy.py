"""Offline policy wiring checks; not a model accuracy benchmark."""
import unittest
from unittest.mock import patch

from src.critic.semantic import PROMPT, build_input
from src.critic.critic import run_critic
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.scouts.trend import run_trend_scout
from src.graph.trend_context import build_trend_context
from tests.test_trend_context import evidence
from tests.test_local import article


class TrendResearchPolicyTests(unittest.TestCase):
    def test_missing_response_does_not_drop_sourced_reference(self):
        bundle = evidence()
        bundle['request']['research']['reference_date'] = '2026-10-01'
        ctx = build_trend_context(bundle['request'], bundle['results']['quant'])
        def detail(case, source, *_):
            return {'status': 'text_corroborated', 'event_verified': False,
                    'demographic_response_established': False, 'response_signals': [],
                    'source_ids': [source['source_id']], 'reported_mechanisms': [
                        {'mechanism': 'mission_journey', 'matched_terms': ['미션'], 'source_ids': [source['source_id']]}]}
        with patch('src.scouts.search_runtime.news', return_value=[article('서울 게임 팝업 미션 체험')]), \
             patch('src.scouts.search_runtime.videos', return_value=[]):
            bundle['results']['trend'] = run_trend_scout(bundle['request'], context=ctx, detail_reader=detail)
        brief = generate_brief(bundle)
        card = next(c for c in brief['trend_patterns'] if c.get('type') == 'reference_case')
        self.assertTrue(card['audience_fit'])
        self.assertTrue(card['adaptation_hypotheses'])
        self.assertIn('확보 가능할 때 보조 근거', card['audience_fit'][0]['next_check'])
        rendered = render_markdown(brief)
        self.assertIn('미확보만으로 사례를 제외하지 않습니다', rendered)
        self.assertIn('활용을 막는 조건은 아닙니다', rendered)
        self.assertFalse(card['case_detail']['event_verified'])
        bundle['module_status']['trend'] = bundle['results']['trend']['status']
        payload = build_input(bundle, run_critic(bundle))
        claim = next(c for c in payload['claims'] if c['claim_id'].startswith('trend:insight:'))
        self.assertIn('quant-source', claim['allowed_source_ids'])
        self.assertEqual(set(claim['allowed_source_ids']), {e['source_id'] for e in claim['evidence']})
        bundle['results']['trend']['insights'][0]['context_source_refs'].append({'module': 'quant', 'source_id': 'invented'})
        claim = next(c for c in build_input(bundle, run_critic(bundle))['claims'] if c['claim_id'].startswith('trend:insight:'))
        self.assertNotIn('invented', claim['allowed_source_ids'])

    def test_prompt_preserves_policy_boundaries(self):
        for instruction in ('not demonstrated customer response', 'not a rejection or mandatory task',
                            'community posts support only', 'not proof of popularity or effectiveness',
                            'Missing mechanism provenance', 'still needs preference evidence'):
            self.assertIn(instruction, PROMPT)
