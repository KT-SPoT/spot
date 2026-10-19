import unittest
from unittest.mock import patch

from src.brief.pipeline import enrich_brief, execution_review, synthesis_enabled
from src.brief.connection_synthesis import run_connection_synthesis
from src.graph.graph import brief_node, build_graph
import tests.test_connection_synthesis as examples
from tests.test_regional_synthesis import review


class BriefPipelineTests(unittest.TestCase):
    def setUp(self):
        fixture=examples.ConnectionSynthesisTests();fixture.setUp()
        self.brief,self.baseline=fixture.brief,fixture.base
        self.connections=run_connection_synthesis(self.brief,self.baseline,caller=fixture.connection,reviewer=review)
        self.env={'SPOT_BRIEF_SYNTHESIS':'connections','SPOT_SCOUT_MODE':'live',
                  'SPOT_SEMANTIC_MODE':'shadow','SPOT_CRITIC_PROFILE':'research'}

    def test_offline_and_disabled_modes_preserve_brief_without_paid_calls(self):
        for changes in ({'SPOT_BRIEF_SYNTHESIS':'off'},{'SPOT_SCOUT_MODE':'offline'},
                        {'SPOT_SCOUT_MODE':'mock'},{'SPOT_SCOUT_MODE':''},
                        {'SPOT_SEMANTIC_MODE':'off'},{'SPOT_CRITIC_PROFILE':'evidence'}):
            with patch.dict('os.environ',{**self.env,**changes}),patch('src.brief.pipeline.run_synthesis') as model:
                self.assertFalse(synthesis_enabled())
                self.assertEqual(enrich_brief(self.brief),self.brief)
                model.assert_not_called()

    def test_baseline_failure_keeps_sources_and_does_not_start_connection_calls(self):
        failed={'performed':False,'code':'PROVIDER_TIMEOUT','call_count':1,'insights':[]}
        with patch.dict('os.environ',self.env),patch('src.brief.pipeline.run_synthesis',return_value=failed), \
             patch('src.brief.pipeline.run_connection_synthesis') as model:
            output=enrich_brief(self.brief)
        self.assertEqual(output['unique_local_signals'],self.brief['unique_local_signals'])
        self.assertEqual(output['trend_patterns'],self.brief['trend_patterns'])
        self.assertEqual(output['regional_synthesis']['code'],'PROVIDER_TIMEOUT')
        model.assert_not_called()

    def test_connection_failure_keeps_reviewed_baseline_and_records_diagnostics(self):
        failed={'performed':False,'code':'PROVIDER_HTTP_ERROR','call_count':1,'insights':[]}
        with patch.dict('os.environ',self.env),patch('src.brief.pipeline.run_synthesis',return_value=self.baseline), \
             patch('src.brief.pipeline.run_connection_synthesis',return_value=failed):
            output=enrich_brief(self.brief)
        self.assertEqual(len(output['research_implications']),1)
        self.assertEqual(output['connection_synthesis']['code'],'PROVIDER_HTTP_ERROR')
        self.assertEqual(execution_review(output)['call_count'],3)
        self.assertFalse(execution_review(output)['truth_verified'])

    def test_graph_brief_node_applies_both_stages_after_exclusion_and_reports_calls(self):
        state={'request':{'research':{'reference_date':'2026-10-04'}},
            'research_bundle':{'results':{'local':{'status':'partial'}},'module_status':{'local':'partial'}},
            'critic_result':{'checks':{'excluded_modules':['local']},'warnings':[]}}
        with patch.dict('os.environ',self.env),patch('src.graph.graph.generate_brief',return_value=self.brief) as generate, \
             patch('src.brief.pipeline.run_synthesis',return_value=self.baseline), \
             patch('src.brief.pipeline.run_connection_synthesis',return_value=self.connections):
            output=brief_node(state)
        self.assertEqual(generate.call_args.args[0]['results']['local']['status'],'failed')
        self.assertEqual(state['research_bundle']['results']['local']['status'],'partial')
        self.assertEqual(len(output['research_brief']['research_implications']),3)
        self.assertEqual(output['critic_result']['checks']['semantic_review']['call_count'],4)
        self.assertTrue(output['critic_result']['checks']['semantic_review']['performed'])

    def test_explicit_graph_disable_overrides_enabled_environment(self):
        state={'request':{},'research_bundle':{},'critic_result':{'checks':{}}}
        with patch.dict('os.environ',self.env),patch('src.graph.graph.generate_brief',return_value=self.brief), \
             patch('src.graph.graph.enrich_brief') as paid:
            output=brief_node(state,allow_synthesis=False)
        self.assertEqual(output['research_brief'],self.brief)
        paid.assert_not_called()

    def test_graph_does_not_duplicate_old_case_critic_when_two_stage_reading_is_enabled(self):
        request={'request_id':'pipeline-test'}
        progress=[]
        with patch.dict('os.environ',self.env), \
             patch('src.graph.graph.run_quant_scout',return_value={'status':'success'}) as quant, \
             patch('src.graph.graph.run_local_scout',return_value={'status':'success'}) as local, \
             patch('src.graph.graph.run_trend_scout',return_value={'status':'success'}) as trend, \
             patch('src.graph.graph.trend_context_node',return_value={'trend_context':{}}), \
             patch('src.graph.graph.run_critic',return_value={'status':'manual_review','retry':[], 'checks':{},'warnings':[]}), \
             patch('src.graph.graph.run_semantic') as old_review, \
             patch('src.graph.graph.generate_brief',return_value=self.brief), \
             patch('src.brief.pipeline.run_synthesis',return_value=self.baseline), \
             patch('src.brief.pipeline.run_connection_synthesis',return_value=self.connections):
            output=build_graph(max_retry_rounds=0,progress=lambda *args:progress.append(args)).invoke({'request':request})
        old_review.assert_not_called()
        quant.assert_called_once();local.assert_called_once();trend.assert_called_once()
        self.assertEqual(output['critic_result']['checks']['semantic_review']['call_count'],4)
        self.assertEqual(len(output['research_brief']['research_implications']),3)
        self.assertIn(('brief','completed'),progress)


if __name__=='__main__':unittest.main()
