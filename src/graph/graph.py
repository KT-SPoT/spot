"""LangGraph integration scaffold for SPOT.

Quant and Local run in parallel; Trend consumes their bounded context.
Critic validates evidence and permits one bounded transient-error retry round.
"""

from langgraph.graph import END, START, StateGraph

from src.brief.generator import generate_brief
from copy import deepcopy
from src.critic.critic import run_critic
from src.critic.semantic import run_semantic
from src.validation import validate_scout_result
from src.critic.rules import evaluate_rules
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
        state.get("quant_result"), state.get("local_result"), quant_evidence=state.get("quant_evidence"))}


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


def critic_node(state: SpotState, *, max_retry_rounds=1) -> dict:
    critic = run_critic(state["research_bundle"], retry_count=state.get("retry_count", 0),
                        max_retry_rounds=max_retry_rounds)
    return {"critic_result": critic, "retry_targets": [item["module"] for item in critic["retry"]]}


def retry_node(state: SpotState) -> dict:
    """Retry only selected modules, preserving earlier usable evidence on failure."""
    updates = {"retry_count": state.get("retry_count", 0) + 1}
    history = list(state.get("retry_history", []))
    targets = set(state.get("retry_targets", []))

    def accept(module, candidate):
        previous = state.get(f"{module}_result", {})
        valid = not validate_scout_result(candidate, expected_module=module,
                                           request_id=state["request"]["request_id"])
        candidate_bundle = merge_node({**state, **updates, f"{module}_result": candidate})["research_bundle"]
        unsafe = any(item["level"] == "needs_fix" and item["module"] in (None, module)
                     for item in evaluate_rules(candidate_bundle)["findings"])
        previous_usable = previous.get("status") in ("success", "partial") and previous.get("sources") and previous.get("insights")
        keep_previous = previous_usable and (not valid or unsafe or candidate.get("status") == "failed"
                                             or "MOCK_ONLY_NOT_REAL_DATA" in candidate.get("warnings", []))
        history.append({"module": module, "attempt": updates["retry_count"],
                        "outcome": "retained_previous" if keep_previous else "replaced"})
        if not keep_previous:
            updates[f"{module}_result"] = candidate
        return not keep_previous

    if "quant" in targets:
        evidence = {}
        result = run_quant_scout(state["request"], evidence_sink=evidence.update)
        if accept("quant", result):
            updates["quant_evidence"] = evidence or None
    if "local" in targets:
        accept("local", run_local_scout(state["request"]))
    upstream_changed = any(f"{module}_result" in updates for module in ("quant", "local"))
    context = build_trend_context(state["request"], updates.get("quant_result", state.get("quant_result")),
                                  updates.get("local_result", state.get("local_result")),
                                  quant_evidence=updates.get("quant_evidence", state.get("quant_evidence")))
    updates["trend_context"] = context
    if "trend" in targets:
        accept("trend", run_trend_scout(state["request"], context=context))
    if upstream_changed and "trend_result" not in updates:
        trend = deepcopy(state.get("trend_result", {}))
        trend.setdefault("warnings", []).append("UPSTREAM_CONTEXT_CHANGED_TREND_NOT_REFRESHED")
        updates["trend_result"] = trend
    updates["retry_history"] = history
    return updates


def brief_node(state: SpotState) -> dict:
    bundle = deepcopy(state["research_bundle"])
    excluded = state.get("critic_result", {}).get("checks", {}).get("excluded_modules", [])
    for module in excluded:
        if isinstance(bundle.get("results", {}).get(module), dict):
            bundle["results"][module]["status"] = "failed"
            bundle["module_status"][module] = "failed"
    return {"research_brief": generate_brief(bundle, state.get("critic_result"),
                                            quant_evidence=None if "quant" in excluded else state.get("quant_evidence"))}


def build_graph(*, max_retry_rounds=1, semantic_caller=None, semantic_mode=None, progress=None):
    if type(max_retry_rounds) is not int or max_retry_rounds not in (0, 1):
        raise ValueError("max_retry_rounds must be 0 or 1")
    graph = StateGraph(SpotState)

    def observed(name, fn):
        def run(state):
            if progress:
                progress(name, "running")
            try:
                result = fn(state)
            except Exception:
                if progress:
                    progress(name, "failed")
                raise
            scout = result.get(f"{name}_result", {})
            if progress:
                progress(name, scout.get("status", "completed"))
            return result
        return run

    graph.add_node("quant", observed("quant", quant_node))
    graph.add_node("local", observed("local", local_node))
    graph.add_node("trend", observed("trend", trend_node))
    graph.add_node("trend_context", trend_context_node)
    graph.add_node("merge", observed("merge", merge_node))
    graph.add_node("critic", observed("critic", lambda state: critic_node(state, max_retry_rounds=max_retry_rounds)))
    graph.add_node("retry", observed("retry", retry_node))
    def semantic_node(state):
        critic = deepcopy(state['critic_result'])
        critic['checks']['semantic_review'] = run_semantic(state['research_bundle'], critic,
            caller=semantic_caller, mode=semantic_mode, quant_evidence=state.get('quant_evidence'))
        return {'critic_result': critic}
    graph.add_node("semantic", observed("semantic", semantic_node))
    graph.add_node("brief", observed("brief", brief_node))

    # Gather independent measurements before context-dependent discovery.
    graph.add_edge(START, "quant")
    graph.add_edge(START, "local")
    graph.add_edge(["quant", "local"], "trend_context")
    graph.add_edge("trend_context", "trend")

    # Trend starts only after both upstream results are available.
    graph.add_edge("trend", "merge")
    graph.add_edge("merge", "critic")

    graph.add_conditional_edges("critic", lambda state: "retry" if state["critic_result"]["status"] == "retry_required" else "semantic")
    graph.add_edge("retry", "merge")
    graph.add_edge("semantic", "brief")
    graph.add_edge("brief", END)

    return graph.compile()
