"""Offline Critic draft preview. No source fetching, graph routing or quality approval."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from src.validation import validate_scout_result


MODULES = ("quant", "local", "trend")
KST = timezone(timedelta(hours=9))
PENDING_CHECKS = [
    "원문이 주장 내용을 실제로 뒷받침하는지 확인",
    "지역 관측을 사용한 응용 질문인지, 지역명만 바꿔도 같은 제안인지 검토",
    "전국 사례의 참여 방식과 매장 지역·고객 관측의 연결 검토",
    "계획·운영 단계, 인구 모집단, 미확인 호응·효과를 구분",
]


def _publication_date(value):
    """Accept contract dates or timezone-aware datetimes; normalize datetimes to KST."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("date must be a string")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime requires a timezone")
    return parsed.astimezone(KST).date()


def evaluate_rules(bundle):
    """Return a non-mutating preview report, separate from CriticResult v0.1.

    rule_status: pass / manual_review / needs_fix. quality_status is always
    manual_review because semantic quality and factual truth are not evaluated.
    Counts are diagnostics; no new Scout minimum-count contract is imposed.
    """
    findings = []
    counts = {}

    def add(rule, code, module, level, path, message):
        findings.append({"rule_id": rule, "code": code, "module": module,
                         "level": level, "path": path, "message": message})

    def finish():
        levels = {item["level"] for item in findings}
        status = "needs_fix" if "needs_fix" in levels else (
            "manual_review" if "manual_review" in levels else "pass")
        return {"policy_version": "draft-0.1", "preview_only": True,
                "request_id": bundle.get("request_id") if isinstance(bundle, dict) else None,
                "rule_status": status, "quality_status": "manual_review",
                "findings": findings, "counts": counts,
                "pending_checks": list(PENDING_CHECKS)}

    if not isinstance(bundle, dict):
        add("R00", "INVALID_BUNDLE", None, "needs_fix", "bundle", "ResearchBundle은 object여야 한다.")
        return finish()
    request = bundle.get("request")
    results = bundle.get("results")
    statuses = bundle.get("module_status")
    request_id = bundle.get("request_id")
    if (bundle.get("schema_version") != "0.1" or not isinstance(request_id, str)
            or not request_id.strip() or not isinstance(request, dict)
            or not isinstance(results, dict) or not isinstance(statuses, dict)):
        add("R00", "INVALID_BUNDLE", None, "needs_fix", "bundle", "bundle 버전·요청 ID·request·results·module_status를 확인한다.")
        return finish()
    if request.get("request_id") != request_id:
        add("R00", "REQUEST_ID_MISMATCH", None, "needs_fix", "request.request_id", "요청과 bundle ID가 다르다.")
    research = request.get("research")
    try:
        if not isinstance(research, dict):
            raise ValueError("research must be an object")
        raw_reference = research.get("reference_date")
        if not isinstance(raw_reference, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_reference):
            raise ValueError("reference_date requires YYYY-MM-DD")
        reference = date.fromisoformat(raw_reference)
        days = research.get("lookback_days")
        if type(days) is not int or days < 0:
            raise ValueError("lookback_days requires a nonnegative integer")
        start = reference - timedelta(days=days)
    except (ValueError, TypeError, OverflowError) as error:
        add("R00", "INVALID_RESEARCH_PERIOD", None, "needs_fix", "request.research", str(error))
        return finish()

    for module in MODULES:
        result = results.get(module)
        root = f"results.{module}"
        errors = validate_scout_result(result, expected_module=module, request_id=request_id)
        if errors:
            add("R01", "INVALID_SCOUT_RESULT", module, "needs_fix", root, "; ".join(errors))
            continue
        if statuses.get(module) != result["status"]:
            add("R01", "MODULE_STATUS_MISMATCH", module, "needs_fix", f"module_status.{module}", "Merge 상태와 Scout 상태가 다르다.")
        if result["status"] != "success":
            add("R02", "SCOUT_NOT_SUCCESS", module, "manual_review", root + ".status", "partial/failed를 전체 실패로 단정하지 않고 부족 사유를 확인한다.")
        if result["errors"]:
            add("R02", "SCOUT_ERRORS_PRESENT", module, "manual_review", root + ".errors", "Scout 오류를 확인한다.")
        warning_codes = [item if isinstance(item, str) else item.get("code", "")
                         for item in result["warnings"] if isinstance(item, (str, dict))]
        if any(isinstance(code, str) and code.startswith("MOCK_") for code in warning_codes):
            add("R02", "MOCK_EVIDENCE", module, "manual_review", root + ".warnings", "mock을 실제 조사 근거로 사용할 수 없다.")
        if "SYNTHETIC_TEST_DATA" in warning_codes:
            add("R02", "SYNTHETIC_EVIDENCE", module, "info", root + ".warnings", "규칙 검증 전용 합성 데이터이며 실제 근거가 아니다.")
        if warning_codes and any(code != "SYNTHETIC_TEST_DATA" for code in warning_codes):
            add("R02", "SCOUT_WARNINGS_PRESENT", module, "manual_review", root + ".warnings", "고정 사례·미지원 지역·관련성 미검토 등 Scout 경고를 사람이 확인한다.")

        sources = result["sources"]
        insights = result["insights"]
        source_map = {}
        urls = set()
        dated_sources = {}
        cited = set()
        if not insights or not sources:
            add("R03", "EMPTY_EVIDENCE", module, "manual_review", root, "인사이트 또는 출처가 없다. 추가 확보 가능 여부를 확인한다.")
        for index, source in enumerate(sources):
            path = root + f".sources[{index}]"
            sid = source.get("source_id")
            if not isinstance(sid, str) or not sid.strip():
                add("R04", "SOURCE_ID_UNAVAILABLE", module, "manual_review", path, "출처 ID 미확보로 주장별 참조를 확인할 수 없다.")
            elif sid in source_map:
                add("R04", "DUPLICATE_SOURCE_ID", module, "needs_fix", path, "같은 출처 ID가 중복돼 참조가 모호하다.")
            else:
                source_map[sid] = source
            for field in ("source_name", "source_type"):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    add("R04", "SOURCE_METADATA_UNAVAILABLE", module, "manual_review", path + "." + field, "출처 이름·종류 미확보 사유를 확인한다.")
            url = source.get("source_url")
            if url is None or url == "":
                add("R04", "SOURCE_URL_UNAVAILABLE", module, "manual_review", path + ".source_url", "API 등 URL 미확보 사유와 별도 provenance를 확인한다.")
            else:
                try:
                    parsed = urlsplit(url) if isinstance(url, str) else None
                    valid_url = parsed is not None and parsed.scheme in ("http", "https") and bool(parsed.hostname)
                except ValueError:
                    valid_url = False
                if not valid_url:
                    add("R04", "INVALID_SOURCE_URL", module, "needs_fix", path + ".source_url", "출처 URL 형식이 잘못됐다. 접근 여부는 검사하지 않는다.")
                elif url in urls:
                    add("R06", "DUPLICATE_SOURCE_URL", module, "manual_review", path + ".source_url", "같은 URL을 여러 독립 근거로 계산하지 않는다.")
                else:
                    urls.add(url)
            collected = source.get("collected_at")
            try:
                if not collected:
                    add("R04", "COLLECTION_TIME_UNAVAILABLE", module, "manual_review", path + ".collected_at", "실제 수집 시각 미확보 사유를 확인한다.")
                else:
                    if not isinstance(collected, str):
                        raise ValueError("collection time must be a string")
                    stamp = datetime.fromisoformat(collected)
                    if stamp.tzinfo is None or stamp.utcoffset() is None:
                        raise ValueError("collection time requires a timezone")
            except ValueError:
                add("R04", "INVALID_COLLECTION_TIME", module, "needs_fix", path + ".collected_at", "수집 시각은 timezone을 포함한 ISO datetime이어야 한다.")
            if module in ("local", "trend"):
                try:
                    published = _publication_date(source.get("published_at"))
                    if published is None:
                        add("R05", "PUBLICATION_DATE_UNAVAILABLE", module, "manual_review", path + ".published_at", "게시일이 없으므로 최신성을 확정할 수 없다.")
                    elif published > reference:
                        add("R05", "FUTURE_PUBLICATION", module, "needs_fix", path + ".published_at", "분석 기준일 이후 자료가 포함됐다.")
                    elif published < start:
                        add("R05", "OUTSIDE_LOOKBACK", module, "manual_review", path + ".published_at", "요청 기간보다 오래된 자료다. 배경자료 여부를 확인한다.")
                    elif isinstance(sid, str):
                        dated_sources[sid] = published
                except ValueError:
                    add("R05", "INVALID_PUBLICATION_DATE", module, "needs_fix", path + ".published_at", "게시일 날짜 또는 datetime 형식이 잘못됐다.")

        def check_refs(refs, path):
            if not isinstance(refs, list) or not refs:
                add("R04", "EVIDENCE_LINK_UNAVAILABLE", module, "manual_review", path, "주장별 출처 연결이 미확보됐다. Quant metric_refs 연결은 별도 설계한다.")
                return
            for sid in refs:
                if not isinstance(sid, str) or sid not in source_map:
                    add("R04", "BROKEN_SOURCE_REFERENCE", module, "needs_fix", path, "참조한 출처 ID가 해당 모듈 sources에 없다.")
                else:
                    cited.add(sid)

        event_keys = set()
        for index, insight in enumerate(insights):
            path = root + f".insights[{index}]"
            check_refs(insight.get("source_ids"), path + ".source_ids")
            event_key = insight.get("event_key")
            if isinstance(event_key, str) and event_key:
                if event_key in event_keys:
                    add("R06", "DUPLICATE_EVENT_KEY", module, "needs_fix", path + ".event_key", "동일 사건을 인사이트 여러 건으로 계산했다.")
                event_keys.add(event_key)
            if module == "local":
                from src.scouts.local_evidence import nonfactual_change
                if insight.get("evidence_role") == "direct_change" and nonfactual_change(insight.get("evidence") or ""):
                    add("R07", "NONFACTUAL_LOCAL_CHANGE", module, "manual_review", path, "질문·희망·당위 표현을 실제 지역 변화로 사용할 수 없다. 해당 항목을 변화 요약에서 제외한다.")
                if not insight.get("change_state"):
                    add("R07", "CHANGE_STAGE_UNAVAILABLE", module, "manual_review", path, "계획·선정·운영 단계 미확보. 표현 의미는 사람이 확인한다.")
                if not (insight.get("locality_tags") or insight.get("locality_tag")):
                    add("R07", "LOCALITY_TAG_UNAVAILABLE", module, "manual_review", path, "지역 태그 미확보. 태그 존재만으로 지역 구체성을 승인하지 않는다.")

        if module == "trend":
            patterns = result.get("patterns")
            if not isinstance(patterns, list) or not patterns:
                add("R08", "PATTERN_UNAVAILABLE", module, "manual_review", root + ".patterns", "반복 패턴이 미확보됐다.")
            else:
                case_ids = {item["case_id"] for item in insights if isinstance(item.get("case_id"), str)}
                for index, pattern in enumerate(patterns):
                    path = root + f".patterns[{index}]"
                    if not isinstance(pattern, dict):
                        add("R08", "INVALID_PATTERN", module, "needs_fix", path, "패턴은 object여야 한다.")
                        continue
                    check_refs(pattern.get("example_source_ids"), path + ".example_source_ids")
                    examples = pattern.get("example_case_ids")
                    count = pattern.get("evidence_count")
                    if type(count) is not int or count < 0:
                        add("R08", "INVALID_PATTERN_COUNT", module, "needs_fix", path, "evidence_count는 음수가 아닌 정수여야 한다.")
                    if not isinstance(examples, list) or not examples:
                        add("R08", "PATTERN_CASE_TRACE_UNAVAILABLE", module, "manual_review", path, "출처 수와 사례 수는 다를 수 있다. 사례 연결 없이 횟수를 확정하지 않는다.")
                    elif any(not isinstance(cid, str) for cid in examples):
                        add("R08", "INVALID_PATTERN_CASE_IDS", module, "needs_fix", path, "사례 ID 배열 형식이 잘못됐다.")
                    else:
                        unique = set(examples)
                        if len(unique) != len(examples) or count != len(unique):
                            add("R08", "PATTERN_COUNT_MISMATCH", module, "needs_fix", path, "반복 횟수와 중복 제거한 사례 수가 다르다.")
                        if not unique.issubset(case_ids):
                            add("R08", "BROKEN_PATTERN_CASE_REFERENCE", module, "needs_fix", path, "패턴 사례 ID가 해당 모듈 insights에 없다.")
                        if len(unique) < 2:
                            add("R08", "PATTERN_NOT_REPEATED", module, "manual_review", path, "1개 사례만으로 반복 패턴을 확정할 수 없다.")
        if module in ("local", "trend") and not cited.intersection(dated_sources):
            add("R05", "NO_RECENT_CITED_SOURCE", module, "manual_review", root, "실제 참조된 출처 중 요청 기간 내 날짜가 확인된 자료가 없다.")
        counts[module] = {"insights": len(insights), "sources": len(sources),
                          "unique_source_urls": len(urls), "cited_sources": len(cited),
                          "recent_cited_sources": len(cited.intersection(dated_sources)) if module != "quant" else None}
    return finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    report = evaluate_rules(bundle)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["rule_status"] == "needs_fix" else 0


if __name__ == "__main__":
    raise SystemExit(main())
