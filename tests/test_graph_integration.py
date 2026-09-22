"""Integration with synthetic outputs, never live Scout API calls."""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from src.contracts import mock_scout_result
from src.graph.graph import build_graph, merge_node


class GraphIntegrationTest(unittest.TestCase):
    def fixtures(self):
        request = {"schema_version": "0.1", "request_id": "synthetic-001"}
        results = {}
        for module, status in zip(("quant", "local", "trend"), ("success", "partial", "failed")):
            results[module] = mock_scout_result(module, request["request_id"])
            results[module].update(status=status, metrics={"synthetic": True})
        return request, results

    def test_merge_preserves_full_results_without_mutation(self):
        request, results = self.fixtures()
        state = {"request": request, **{f"{m}_result": r for m, r in results.items()}}
        before = copy.deepcopy(state)
        bundle = merge_node(state)["research_bundle"]
        self.assertEqual(bundle["results"], results)
        self.assertEqual(bundle["request"], request)
        self.assertEqual(bundle["module_status"], {m: r["status"] for m, r in results.items()})
        self.assertEqual(state, before)

    def test_mixed_statuses_reach_brief_after_join(self):
        request, results = self.fixtures()
        with ExitStack() as stack:
            for module, result in results.items():
                stack.enter_context(patch(f"src.graph.graph.run_{module}_scout", return_value=result))
            events = list(build_graph().stream({"request": request}, stream_mode="updates"))
        nodes = [node for event in events for node in event]
        self.assertCountEqual(nodes[:3], ["quant", "local", "trend"])
        self.assertEqual(nodes[3:], ["merge", "critic", "brief"])
        bundle = events[3]["merge"]["research_bundle"]
        self.assertEqual(bundle["results"], results)
        self.assertEqual(events[-1]["brief"]["research_brief"]["status"], "mock")

    def test_uncaught_exception_currently_aborts_before_merge(self):
        request, results = self.fixtures()
        for failing_module in results:
            with self.subTest(module=failing_module), ExitStack() as stack:
                for module, result in results.items():
                    runner = stack.enter_context(patch(f"src.graph.graph.run_{module}_scout", return_value=result))
                    if module == failing_module:
                        runner.side_effect = RuntimeError("synthetic API failure")
                merge = stack.enter_context(patch("src.graph.graph.merge_node"))
                brief = stack.enter_context(patch("src.graph.graph.mock_brief"))
                with self.assertRaisesRegex(RuntimeError, "synthetic API failure"):
                    build_graph().invoke({"request": request})
                merge.assert_not_called()
                brief.assert_not_called()
