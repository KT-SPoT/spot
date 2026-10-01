"""Build a bounded internal Trend context without changing SpotRequest v0.1."""
from copy import deepcopy
from urllib.parse import urlsplit

from src.validation import validate_scout_result


def build_trend_context(request, quant=None, local=None):
    output = {"request_id": request.get("request_id"), "population_signals": [],
              "local_signals": [], "sources": {"quant": [], "local": []},
              "module_status": {}, "limitations": [
                  "인구 구성은 실제 구매 고객이나 선호를 뜻하지 않습니다.",
                  "매출·유동·주거·직장 인구는 서로 다른 모집단입니다.",
                  "자료 생성일을 지표 기준 시점으로 바꾸지 않습니다."]}
    valid = {}
    for module, result in (("quant", quant), ("local", local)):
        if not isinstance(result, dict):
            output["module_status"][module] = "unavailable"
            continue
        output["module_status"][module] = result.get("status", "unavailable")
        if (validate_scout_result(result, expected_module=module, request_id=request.get("request_id"))
                or result.get("status") == "failed" or "MOCK_ONLY_NOT_REAL_DATA" in result.get("warnings", [])):
            continue
        sources = []
        for source in result.get("sources", []):
            url = source.get("source_url", "")
            try:
                parts = urlsplit(url)
            except (ValueError, TypeError):
                continue
            if parts.scheme in ("http", "https") and parts.hostname and not parts.username and source.get("source_id"):
                # Only provenance, never raw provider archives or credential fields.
                sources.append({k: deepcopy(source[k]) for k in
                    ("source_id", "source_name", "source_type", "published_at", "collected_at") if k in source})
        if sources:
            output["sources"][module] = sources[:20]
            valid[module] = result
    if "quant" in valid:
        result = valid["quant"]
        metrics = result.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        for population, gender_key, age_key in (
                ("floating_population", "dominant_floating_gender", "dominant_floating_age"),
                ("sales", "dominant_sales_gender", "dominant_sales_age")):
            gender, age = metrics.get(gender_key), metrics.get(age_key)
            if gender not in ("male", "female"):
                gender = None
            if age not in ("under_10", "teens", "20s", "30s", "40s", "50s", "60_plus"):
                age = None
            if gender or age:
                output["population_signals"].append({"population_kind": population,
                    "dominant_gender": gender, "dominant_age": age,
                    "gender_share_pct": None, "age_share_pct": None, "reference_period": None,
                    "metric_refs": [key for key in (gender_key, age_key) if metrics.get(key) is not None],
                    "source_ids": [s["source_id"] for s in output["sources"]["quant"]],
                    "area_scope": deepcopy({k: v for k, v in result.get("query_context", {}).items()
                        if k in ("radius_m", "lat", "lng", "area_name")})})
        output["limitations"].append("현재 Quant 공통 결과의 주요 성별·연령을 사용합니다. 전체 비율 분포·모집단별 기준 시점은 미확보로 표시합니다.")
    if "local" in valid:
        available_ids = {s["source_id"] for s in output["sources"]["local"]}
        for item in valid["local"].get("insights", []):
            if item.get("verification_status") not in ("text_corroborated", "context_corroborated"):
                continue
            ids = item.get("source_ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(sid, str) for sid in ids) or not set(ids).issubset(available_ids):
                continue
            output["local_signals"].append({k: deepcopy(item[k]) for k in
                ("insight_id", "title", "evidence", "evidence_role", "change_state", "source_ids",
                 "published_at", "date_basis", "context_note", "verification_status") if k in item})
            if len(output["local_signals"]) >= 10:
                break
    return output
