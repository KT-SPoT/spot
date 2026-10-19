"""Run integrated Scouts and save evidence plus a Research Brief draft.

Offline mode runs the actual Local/Trend code and actual Quant missing-key path.
It disables dotenv loading and credentials, rather than fabricating Quant data.
"""

import argparse
import json
import os
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from src.critic.rules import evaluate_rules
from src.brief.renderer import render_markdown
from src.graph.graph import build_graph
from src.validation import validate_scout_result


def run_smoke(request, *, mode="offline", progress=None):
    if mode not in ("offline", "live"):
        raise ValueError("mode must be offline or live")
    store = request.get("store") or {}
    if mode == "live" and store.get("address") == "부산광역시 강서구 명지국제신도시":
        raise ValueError("실제 조사 주소·좌표를 확정한 입력 파일을 사용하세요.")
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {
            "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
        }))
        if mode == "offline":
            stack.enter_context(patch.dict(os.environ, {
                "KAKAO_REST_API_KEY": "", "SBIZ365_CERT_KEY": "",
                "SPOT_SCOUT_MODE": "offline",
            }))
            stack.enter_context(patch("src.scouts.quant.load_dotenv"))
        state = build_graph(progress=progress).invoke({"request": request})
    bundle = state["research_bundle"]
    validation = {
        module: validate_scout_result(result, expected_module=module,
                                      request_id=request["request_id"])
        for module, result in bundle["results"].items()
    }
    return {
        "mode": mode,
        "graph_completed": True,
        "all_contracts_valid": not any(validation.values()),
        "validation_errors": validation,
        "module_status": bundle["module_status"],
        "critic_is_mock": False,
        "brief_is_mock": state["research_brief"].get("status") == "mock",
        "state": state,
        "critic_rule_preview": evaluate_rules(bundle),
    }


def save_run(run, output):
    output.mkdir(parents=True, exist_ok=True)
    state = run["state"]
    artifacts = {
        "request": state["request"],
        "research_bundle": state["research_bundle"],
        "critic_result": state["critic_result"],
        "research_brief_mock" if run["brief_is_mock"] else "research_brief": state["research_brief"],
        "critic_rule_preview": run["critic_rule_preview"],
        "validation": {k: v for k, v in run.items()
                       if k not in ("state", "critic_rule_preview")},
    }
    artifacts.update({f"{module}_result": result
                      for module, result in state["research_bundle"]["results"].items()})
    for name, value in artifacts.items():
        (output / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not run["brief_is_mock"]:
        (output / "RESEARCH_BRIEF.md").write_text(render_markdown(state["research_brief"]), encoding="utf-8")
    lines = ["# Scout 통합 실행 요약", "",
             f"- 실행 모드: {run['mode']}",
             f"- Graph 종료까지 도달: {run['graph_completed']}",
             f"- 공통 계약 검증 통과: {run['all_contracts_valid']}",
             "- Critic은 실제 규칙을 검사합니다. 의미·사실 검토는 미완료이며 Research Brief는 조사 초안입니다.",
             "- 별도 Critic 기준표 검사는 품질 승인이나 사실 검증을 대신하지 않습니다.",
             "", "| 모듈 | 상태 | 인사이트 | 출처 |", "|---|---|---:|---:|"]
    for module, result in state["research_bundle"]["results"].items():
        lines.append(f"| {module} | {result['status']} | {len(result['insights'])} | {len(result['sources'])} |")
    for module, result in state["research_bundle"]["results"].items():
        lines.extend(["", f"## {module}", "", result["summary"], ""])
        for item in result["insights"]:
            lines.append("- " + str(item.get("statement") or item.get("evidence") or item.get("title") or item.get("case_name") or item.get("name") or item.get("case_id")))
        for label in ("warnings", "errors"):
            if result[label]:
                lines.extend(["", f"{label}:"])
                lines.extend("- " + (item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)) for item in result[label])
    (output / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        run = run_smoke(request, mode=args.mode)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    save_run(run, args.output)
    print(json.dumps({k: v for k, v in run.items()
                      if k not in ("state", "critic_rule_preview")}, ensure_ascii=False, indent=2))
    # A failed Scout is a captured outcome, not a graph/contract failure.
    return 0 if run["all_contracts_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
