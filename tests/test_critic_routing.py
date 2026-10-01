"""Real rule routing and bounded retry scenarios; no live providers."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.critic.critic import run_critic
from src.graph.graph import build_graph

BASE = json.loads((Path(__file__).resolve().parents[1] / 'samples/critic/research_bundle.synthetic.json').read_text())


def failure(result, *, status='failed', code='PROVIDER_HTTP_ERROR', http_status=503):
    result = copy.deepcopy(result)
    result.update(status=status, errors=[{'code':code, 'http_status':http_status}])
    if status == 'failed':
        result.update(insights=[], sources=[], patterns=[], reference_cases=[])
    return result


class CriticRoutingTests(unittest.TestCase):
    def graph(self, local, trend=None, *, max_retry_rounds=1):
        with patch('src.graph.graph.run_quant_scout', return_value=copy.deepcopy(BASE['results']['quant'])) as q, \
             patch('src.graph.graph.run_local_scout', side_effect=local) as l, \
             patch('src.graph.graph.run_trend_scout', side_effect=trend or [copy.deepcopy(BASE['results']['trend'])]) as t:
            output = build_graph(max_retry_rounds=max_retry_rounds).invoke({'request':copy.deepcopy(BASE['request'])})
        return output, q, l, t

    def test_rules_pass_is_real_critic_but_not_quality_approval(self):
        before = copy.deepcopy(BASE)
        critic = run_critic(BASE)
        self.assertEqual(critic['checks']['rules']['rule_status'], 'pass')
        self.assertEqual(critic['status'], 'manual_review')
        self.assertFalse(critic['checks']['semantic_review']['performed'])
        self.assertEqual(critic['retry'], [])
        self.assertNotIn('MOCK_CRITIC', json.dumps(critic))
        self.assertEqual(BASE, before)

    def test_only_transient_errors_retry_never_quota_keys_or_empty_search(self):
        for code, http in [('PROVIDER_HTTP_ERROR',429), ('PROVIDER_HTTP_ERROR',401),
                           ('PROVIDER_HTTP_ERROR',403), ('MISSING_YOUTUBE_API_KEY',None),
                           ('OFFLINE_MODE',None), ('INVALID_PROVIDER_RESPONSE',None),
                           ('SBIZ365_COLLECTION_ERROR',None)]:
            bundle = copy.deepcopy(BASE)
            bundle['results']['local'] = failure(bundle['results']['local'], code=code, http_status=http)
            bundle['module_status']['local']='failed'
            self.assertEqual(run_critic(bundle)['retry'], [], (code,http))
        bundle = copy.deepcopy(BASE)
        bundle['results']['local']=failure(bundle['results']['local'])
        bundle['module_status']['local']='failed'
        self.assertEqual(run_critic(bundle)['retry'][0]['module'],'local')
        self.assertEqual(run_critic(bundle,retry_count=1)['retry'],[])
        self.assertEqual(run_critic(bundle,max_retry_rounds=0)['retry'],[])
        bundle['results']['local']['errors'].append({'code':'PROVIDER_HTTP_ERROR','http_status':429})
        self.assertEqual(run_critic(bundle)['retry'],[])

    def test_single_module_recovers_without_rerunning_others(self):
        good=copy.deepcopy(BASE['results']['local']); bad=failure(good)
        output,q,l,t=self.graph([bad,good])
        self.assertEqual((q.call_count,l.call_count,t.call_count),(1,2,1))
        self.assertEqual(output['retry_count'],1)
        self.assertEqual(output['local_result'],good)
        self.assertEqual(output['critic_result']['status'],'manual_review')
        self.assertIn('UPSTREAM_CONTEXT_CHANGED_TREND_NOT_REFRESHED',output['trend_result']['warnings'])

    def test_retry_failure_preserves_previous_sources_and_stops(self):
        partial=failure(BASE['results']['local'],status='partial')
        output,q,l,t=self.graph([partial,failure(partial)])
        self.assertEqual(l.call_count,2)
        self.assertEqual(output['local_result'],partial)
        self.assertEqual(output['retry_history'][0]['outcome'],'retained_previous')
        self.assertIn('TRANSIENT_RETRY_LIMIT_REACHED',output['critic_result']['warnings'])
        self.assertTrue(output['research_brief']['local_changes'])

    def test_persistent_transient_failure_and_disabled_retries_are_bounded(self):
        bad=failure(BASE['results']['local'])
        output,q,l,t=self.graph([bad,bad])
        self.assertEqual(l.call_count,2)
        self.assertEqual(output['retry_count'],1)
        self.assertEqual(output['critic_result']['retry'],[])
        output,q,l,t=self.graph([bad],max_retry_rounds=0)
        self.assertEqual(l.call_count,1)
        self.assertEqual(output['critic_result']['retry'],[])

    def test_retry_bad_source_cannot_replace_previous_usable_result(self):
        partial=failure(BASE['results']['local'],status='partial')
        corrupt=copy.deepcopy(BASE['results']['local'])
        corrupt['insights'][0]['source_ids']=['missing']
        output,*_=self.graph([partial,corrupt])
        self.assertEqual(output['local_result'],partial)
        self.assertEqual(output['retry_history'][0]['outcome'],'retained_previous')

    def test_retried_trend_receives_new_upstream_context(self):
        local=copy.deepcopy(BASE['results']['local'])
        local['insights'][0].update(verification_status='text_corroborated')
        output,q,l,t=self.graph([failure(local),local],
                               [failure(BASE['results']['trend']),BASE['results']['trend']])
        self.assertEqual((q.call_count,l.call_count,t.call_count),(1,2,2))
        self.assertEqual(t.call_args.kwargs['context'],output['trend_context'])
        self.assertEqual(len(output['trend_context']['local_signals']),1)

    def test_future_or_broken_evidence_is_excluded_not_automatically_researched(self):
        for mutate in ('future','broken'):
            bad=copy.deepcopy(BASE['results']['local'])
            if mutate=='future':bad['sources'][0]['published_at']='2099-01-01'
            else:bad['insights'][0]['source_ids']=['missing']
            output,q,l,t=self.graph([bad])
            self.assertEqual(l.call_count,1)
            self.assertEqual(output['research_brief']['local_changes'],[])
            self.assertIn('local',output['critic_result']['checks']['excluded_modules'])
            self.assertEqual(output['research_bundle']['results']['local'],bad)

    def test_all_failed_or_malformed_input_never_claims_success(self):
        bundle=copy.deepcopy(BASE)
        for module,result in bundle['results'].items():
            bundle['results'][module]=failure(result,code='OFFLINE_MODE',http_status=None)
            bundle['module_status'][module]='failed'
        self.assertEqual(run_critic(bundle)['status'],'failed')
        self.assertEqual(run_critic(None)['status'],'failed')
        for value in (True,-1,2):
            with self.assertRaises(ValueError):build_graph(max_retry_rounds=value)


if __name__=='__main__':unittest.main()
