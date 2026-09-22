"""LangGraph integration scaffold for SPOT.

Week-1 goal:
- prove that three independently owned Scout interfaces can join into one state;
- keep Critic / retry routing replaceable while real Scout PoCs are developed.
"""

from langgraph.graph import END, START, StateGraph

from src.brief.generator import mock_brief
from src.critic.critic import mock_critic
from src.graph.state import SpotState
from src.scouts.local import run_local_scout
from src.scouts.quant import run_quant_scout
from src.scouts.trend import run_trend_scout


def quant_node(state: SpotState) -> dict:
    return {"quant_result": run_quant_scout(state["request"])}


def local_node(state: SpotState) -> dict:
    return {"local_result": run_local_scout(state["request"])}


def trend_node(state: SpotState) -> dict:
    return {"trend_result": run_trend_scout(state["request"])}


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
    request_id = state["request"].get("request_id", "unknown")
    return {"research_brief": mock_brief(request_id)}


def build_graph():
    graph = StateGraph(SpotState)

    graph.add_node("quant", quant_node)
    graph.add_node("local", local_node)
    graph.add_node("trend", trend_node)
    graph.add_node("merge", merge_node)
    graph.add_node("critic", critic_node)
    graph.add_node("brief", brief_node)

    # Fan-out: each Scout owns an independent module.
    graph.add_edge(START, "quant")
    graph.add_edge(START, "local")
    graph.add_edge(START, "trend")

    # Fan-in: wait for all three results before merging.
    graph.add_edge(["quant", "local", "trend"], "merge")
    graph.add_edge("merge", "critic")

    # Week-1 smoke-test path only.
    # Conditional retry routing will replace this direct edge.
    graph.add_edge("critic", "brief")
    graph.add_edge("brief", END)

    return graph.compile()
