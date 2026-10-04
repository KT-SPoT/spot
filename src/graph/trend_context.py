"""Build a bounded internal Trend context without changing SpotRequest v0.1."""
from copy import deepcopy
from urllib.parse import urlsplit

from src.validation import validate_scout_result
from src.brief.generator import generate_brief


def build_trend_context(request, quant=None, local=None, *, quant_evidence=None):
    output = {"request_id": request.get("request_id"), "population_signals": [],
              "local_signals": [], "timing_signals": [], "sources": {"quant": [], "local": []},
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
        for population, day_key, time_key in (
                ('floating_population', 'peak_floating_day', 'peak_floating_time_band'),
                ('sales', 'peak_sales_day', 'peak_sales_time_band')):
            if metrics.get(day_key) or metrics.get(time_key):
                output['timing_signals'].append({'population_kind': population,
                    'peak_day': metrics.get(day_key), 'peak_time_band': metrics.get(time_key),
                    'reference_period': None,
                    'source_ids': [s['source_id'] for s in output['sources']['quant']]})
        if quant_evidence is not None:
            # Reuse coordinate/metric matching and bounded cards, never pass HTML.
            bundle = {'request_id': request['request_id'], 'request': request,
                      'results': {'quant': result}}
            cards = generate_brief(bundle, quant_evidence=quant_evidence)['unique_local_signals']
            for card in cards:
                if 'shares' not in card:
                    continue
                shares = deepcopy(card['shares'])
                gender_keys = [k for k in ('male', 'female') if k in shares]
                age_keys = [k for k in ('under_10', 'teens', '20s', '30s', '40s', '50s', '60_plus') if k in shares]
                # Day/time shares belong to timing, never replace demographics.
                if not gender_keys and not age_keys:
                    continue
                gender = max(gender_keys, key=lambda k: shares[k]['share_pct']) if gender_keys else None
                age = max(age_keys, key=lambda k: shares[k]['share_pct']) if age_keys else None
                profile = {'population_kind': card['population_kind'], 'dominant_gender': gender,
                    'dominant_age': age, 'shares': shares,
                    'gender_share_pct': shares[gender]['share_pct'] if gender else None,
                    'age_share_pct': shares[age]['share_pct'] if age else None,
                    'reference_period': card['reference_period'], 'evidence_basis': card['evidence_basis'],
                    'source_ids': [s['source_id'] for s in card['sources']], 'area_scope': card['scope']}
                index = next((i for i, p in enumerate(output['population_signals'])
                              if p['population_kind'] == card['population_kind']), None)
                if index is not None:
                    previous = output['population_signals'][index]
                    profile['metric_refs'] = previous.get('metric_refs', [])
                    profile['shares'] = {**previous.get('shares', {}), **shares}
                    # Sales gender and age can be separate cards. Retain the
                    # independent other axis instead of clearing its values.
                    for axis, available in (('gender', gender_keys), ('age', age_keys)):
                        if not available:
                            profile['dominant_' + axis] = previous.get('dominant_' + axis)
                            profile[axis + '_share_pct'] = previous.get(axis + '_share_pct')
                    output['population_signals'][index] = profile
                else:
                    output['population_signals'].append(profile)
        output["limitations"].append("소상공인365 관측값을 조사 기준으로 사용합니다. 비율이 없는 항목·표의 미표시 기준 시점은 추정하지 않습니다.")
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
