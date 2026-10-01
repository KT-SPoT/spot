"""LangGraph integration scaffold for SPOT.

Quant and Local run in parallel; Trend consumes their bounded context.
Critic remains a mock review step; Brief cites available evidence.
"""

from langgraph.graph import END, START, StateGraph

from src.brief.generator import generate_brief
from src.critic.critic import mock_critic
from src.graph.state import SpotState
from src.graph.trend_context import build_trend_context
from src.scouts.local import run_local_scout
from src.scouts.quant import run_quant_scout
from src.scouts.trend import run_trend_scout


def quant_node(state: SpotState) -> dict:
    evidence = {}
    result = run_quant_scout(state["request"], evidence_sink=evidence.update)
    return {"quant_result": result, "quant_evidence": evidence or None}


def local_node(state: SpotState) -> dict:
    return {"local_result": run_local_scout(state["request"])}


def trend_node(state: SpotState) -> dict:
    return {"trend_result": run_trend_scout(state["request"], context=state.get("trend_context"))}


def trend_context_node(state: SpotState) -> dict:
    return {"trend_context": build_trend_context(state["request"],
        state.get("quant_result"), state.get("local_result"))}


def merge_node(state: SpotState) -> dict:
    request = state["request"]
    bundle = {
        "schema_version": "0.1",
        "request_id": request.get("request_id", "unknown"),
        "request": request,
        "results": {
            "quant": state.get("quant_result", {}),
            "local": state.get("local_result", {}),
            "trend": state.get("trend_result", {}),
        },
        "module_status": {
            "quant": state.get("quant_result", {}).get("status", "failed"),
            "local": state.get("local_result", {}).get("status", "failed"),
            "trend": state.get("trend_result", {}).get("status", "failed"),
        },
    }
    return {"research_bundle": bundle}


def critic_node(state: SpotState) -> dict:
    return {"critic_result": mock_critic(state["research_bundle"])}


def brief_node(state: SpotState) -> dict:
    return {"research_brief": generate_brief(state["research_bundle"], state.get("critic_result"),
                                            quant_evidence=state.get("quant_evidence"))}


def build_graph():
    graph = StateGraph(SpotState)

    graph.add_node("quant", quant_node)
    graph.add_node("local", local_node)
    graph.add_node("trend", trend_node)
    graph.add_node("trend_context", trend_context_node)
    graph.add_node("merge", merge_node)
    graph.add_node("critic", critic_node)
    graph.add_node("brief", brief_node)

    # Gather independent measurements before context-dependent discovery.
    graph.add_edge(START, "quant")
    graph.add_edge(START, "local")
    graph.add_edge(["quant", "local"], "trend_context")
    graph.add_edge("trend_context", "trend")

    # Trend starts only after both upstream results are available.
    graph.add_edge("trend", "merge")
    graph.add_edge("merge", "critic")

    # Week-1 smoke-test path only.
    # Conditional retry routing will replace this direct edge.
    graph.add_edge("critic", "brief")
    graph.add_edge("brief", END)

    return graph.compile()
