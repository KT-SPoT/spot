"""Evidence-based Research Brief draft; no external API or LLM calls."""

from copy import deepcopy
from math import isfinite
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.critic.rules import evaluate_rules
from src.validation import validate_scout_result
from src.brief.trend_groups import group_coverage
from src.brief.quant_policy import quant_basis
from src.brief.failures import failure_summary
from src.brief.quant_distributions import distribution_cards, valid_share


METRICS = {
    "telecom_store_count": ("핸드폰 소매업 업소 수", "개", "industry"),
    "telecom_store_yoy_percent": ("업소 수 전년동월 대비", "%", "industry"),
    "monthly_avg_sales_10k_krw": ("업소당 월평균 매출액", "만원", "sales"),
    "monthly_avg_sales_transactions": ("업소당 월평균 매출건수", "건", "sales"),
    "daily_avg_floating_population": ("월별 일평균 유동인구", "명", "population"),
    "resident_population": ("주거인구", "명", "resident"),
    "worker_population": ("직장인구", "명", "worker"),
    "household_count": ("세대수", "세대", "area"),
    "school_count": ("학교 수", "개", "area"),
    "subway_station_count": ("지하철역 수", "개", "area"),
    "bus_stop_count": ("버스정류장 수", "개", "area"),
}
AGE_LABELS = {"under_10": "10세 미만", "teens": "10대", "20s": "20대",
              "30s": "30대", "40s": "40대", "50s": "50대", "60_plus": "60대 이상"}
CATEGORY_METRICS = {
    "dominant_floating_gender": ("유동인구 주요 성별", {"male": "남성", "female": "여성"}),
    "dominant_floating_age": ("유동인구 주요 연령대", AGE_LABELS),
    "dominant_sales_gender": ("매출 비중 주요 성별", {"male": "남성", "female": "여성"}),
    "dominant_sales_age": ("매출 비중 주요 연령대", AGE_LABELS),
    "peak_floating_day": ("유동인구 최다 요일", {}),
    "peak_floating_time_band": ("유동인구 최다 시간대", {}),
    "peak_sales_day": ("매출 최다 요일", {}),
    "peak_sales_time_band": ("매출 최다 시간대", {}),
    "dominant_facility_type": ("최다 주요시설 유형", {}),
}
DAY_LABELS = dict(zip(("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
                      ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")))


def _category_label(name, value, labels):
    if name.endswith("_day"):
        return DAY_LABELS.get(value, value)
    if name.endswith("_time_band") and value.count("_") == 1:
        return value.replace("_", "~") + "시"
    return labels.get(value, value)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _safe_source(source):
    source = deepcopy(source)
    url = source.get("source_url")
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.netloc or parts.username:
            return None
        secret_names = {"certkey", "apikey", "api_key", "key", "token", "access_token", "secret"}
        query = [(name, "[REDACTED]" if name.lower() in secret_names else value)
                 for name, value in parse_qsl(parts.query, keep_blank_values=True)]
        source["source_url"] = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    except ValueError:
        return None
    return source


def _period(sections, group):
    population = sections.get("population", {})
    if group in ("industry", "sales"):
        value = sections.get(group, {}).get("derived_selected_area", {}).get("latest_period")
        if isinstance(value, str) and len(value) == 5 and value[2] == ".":
            return f"20{value[:2]}년 {value[3:]}월"
        return value
    if group == "area":
        return sections.get("area", {}).get("derived_selected_area", {}).get("latest_household_period")
    path = {"population": ("floating_population", "monthly_daily_average"),
            "resident": ("resident_population", "trend"),
            "worker": ("worker_population", "trend")}[group]
    periods = population.get(path[0], {}).get(path[1], {}).get("periods", [])
    value = periods[-1] if periods else None
    if group == "population" and isinstance(value, str) and len(value) == 5 and value[2] == ".":
        return f"20{value[:2]}년 {value[3:]}월"
    return value


def generate_brief(bundle, critic_result=None, *, quant_evidence=None):
    """Preserve Brief v0.1 fields; evidence cards carry their own provenance.

    quant_evidence is an optional local provider archive, not a new Scout field.
    Never promote the Mock Critic or a deterministic rule pass to quality approval.
    """
    if not isinstance(bundle, dict) or not isinstance(bundle.get("request_id"), str):
        raise ValueError("ResearchBundle request_id가 필요합니다.")
    request_id = bundle["request_id"]
    request = bundle.get("request", {})
    if not isinstance(request, dict) or request.get("request_id") != request_id:
        raise ValueError("ResearchBundle과 입력의 request_id가 다릅니다.")
    results = bundle.get("results", {})
    if not isinstance(results, dict):
        raise ValueError("ResearchBundle results는 객체여야 합니다.")
    checks = []
    valid = {}
    for module in ("quant", "local", "trend"):
        result = results.get(module, {})
        errors = validate_scout_result(result, expected_module=module, request_id=request_id)
        if errors:
            checks.append(f"{module}: 공통 계약 오류로 요약에서 제외했습니다: {', '.join(errors)}")
            continue
        if result["status"] == "failed":
            checks.append(f"{module}: {failure_summary(module, result['errors'])}")
            continue
        if "MOCK_ONLY_NOT_REAL_DATA" in result["warnings"]:
            checks.append(f"{module}: 실패 또는 Mock 결과로 근거 요약에서 제외했습니다.")
            continue
        valid[module] = result
        if result["status"] == "partial":
            checks.append(f"{module}: partial 결과의 부족 사유를 확인하세요.")
        for issue in result["warnings"] + result["errors"]:
            text = issue.get("message") or issue.get("code") if isinstance(issue, dict) else str(issue)
            checks.append(f"{module}: {text}")

    source_maps = {}
    for module, result in valid.items():
        source_maps[module] = {}
        for source in result["sources"]:
            safe = _safe_source(source)
            if safe and isinstance(safe.get("source_id"), str):
                source_maps[module][safe["source_id"]] = safe
    def sources_for(module, ids):
        if not isinstance(ids, list) or any(not isinstance(sid, str) for sid in ids):
            return []
        return [deepcopy(source_maps.get(module, {})[sid]) for sid in dict.fromkeys(ids)
                if isinstance(sid, str) and sid in source_maps.get(module, {})]

    sections = {}
    if quant_evidence is not None:
        if "quant" not in valid:
            raise ValueError("유효한 Quant 결과 없이 보조자료를 사용할 수 없습니다.")
        from src.brief.quant_evidence import read_quant_evidence
        sections = read_quant_evidence(bundle, quant_evidence)

    quant = valid.get("quant", {})
    metrics = quant.get("metrics", {})
    context = quant.get("query_context", {})
    quant_sources = list(source_maps.get("quant", {}).values())
    facts = []
    if quant_sources and isinstance(metrics, dict):
        for name, (label, unit, group) in METRICS.items():
            value = metrics.get(name)
            if not _number(value):
                continue
            period = _period(sections, group)
            facts.append({"module": "quant", "title": label,
                          "statement": f"{label}: {value:,}{unit}", "value": value, "unit": unit,
                          "metric_refs": [name], "reference_period": period,
                          "scope": f"선택 영역 / 요청 반경 {context.get('radius_m', '미확인')}m",
                          "sources": deepcopy(quant_sources)})
        for name, (label, labels) in CATEGORY_METRICS.items():
            value = metrics.get(name)
            if not isinstance(value, str) or not value.strip():
                continue
            display = _category_label(name, value, labels)
            facts.append({"module": "quant", "title": label,
                          "statement": f"{label}: {display}", "value": display, "unit": "",
                          "reported_value": value, "metric_refs": [name], "reference_period": None,
                          "scope": f"선택 영역 / 요청 반경 {context.get('radius_m', '미확인')}m",
                          "sources": deepcopy(quant_sources)})
        if facts and any(fact["reference_period"] is None for fact in facts):
            checks.append("Quant 지표 기준 시점이 일부 미확보입니다. 조회일·분석 생성일을 지표 기준일로 사용하지 마세요.")
    elif metrics:
        checks.append("Quant 수치의 사용 가능한 출처가 없어 수치 요약에서 제외했습니다.")

    demographics = []
    for field, label, group in (("floating_population", "유동인구", "population"),
                                ("resident_population", "주거인구", "resident"),
                                ("worker_population", "직장인구", "worker")):
        selected = sections.get("population", {}).get(field, {}).get("demographics", {}).get("regions", {}).get("선택 영역", {})
        if not selected or not quant_sources:
            continue
        shares = {key: deepcopy(value) for key, value in selected.items()
                  if isinstance(value, dict) and valid_share(value.get("share_pct"))}
        male = shares.get("male", {}).get("share_pct")
        female = shares.get("female", {}).get("share_pct")
        if shares:
            gender_statement = ', '.join(f'{name} {value:g}%' for name, value in
                                         (("남성", male), ("여성", female)) if value is not None)
            demographics.append({"module": "quant", "title": f"{label} 성별·연령 구성",
                                 "statement": f"{label}: {gender_statement or '성별 비율 미확보; 연령 표 확인'}",
                                 "population_kind": field, "shares": shares,
                                 "reference_period": sections.get("population", {}).get(field, {}).get("demographics", {}).get("reference_period"),
                                 "scope": "선택 영역", "sources": deepcopy(quant_sources)})

    local_changes = []
    distributions = distribution_cards(sections, quant_sources,
                                        f"선택 영역 / 요청 반경 {context.get('radius_m', '미확인')}m")
    for card in facts + demographics + distributions:
        card["evidence_basis"] = quant_basis(card["sources"])
    if any(card['reference_period'] is None for card in distributions):
        checks.append("요일·시간대·매출 구성비의 표 기준 시점이 일부 미확보입니다. 다른 표의 최신 월로 대체하지 않습니다.")
    if demographics and any(card["reference_period"] is None for card in demographics):
        checks.append("성별·연령 표의 기준 시점이 미확보입니다. 다른 인구 추이 표의 최신 월이나 분석 생성일을 비율의 기준일로 사용하지 마세요.")
    local_context = []
    for item in valid.get("local", {}).get("insights", []):
        if item.get("article_checked") and item.get("verification_status") not in ("text_corroborated", "context_corroborated"):
            checks.append("Local 원문·게시일 대조가 부족한 검색 후보를 지역 변화 요약에서 제외했습니다. 수집 결과의 verification_log를 확인하세요.")
            continue
        ids = item.get("source_ids", [])
        sources = sources_for("local", ids)
        if not sources or len(sources) != len(set(ids)):
            checks.append("Local의 출처 연결이 불완전한 주장을 요약에서 제외했습니다.")
            continue
        card = deepcopy(item)
        card.update(module="local", sources=sources,
                    scope=("원문 보도 내용 대조; 실제 사건·점포 반경 관련성 별도 확인"
                           if item.get("article_checked") else "Scout가 보고한 지역 범위; 점포 반경 관련성 별도 확인"))
        if item.get("evidence_role") in ("surrounding_context", "background"):
            card["scope"] = ("같은 행정구역의 보조 맥락; 거리·생활권 연결·점포 영향 미확인"
                             if item["evidence_role"] == "surrounding_context" else "지역 설명을 위한 배경 자료; 최근 변화로 집계하지 않음")
            local_context.append(card)
        else:
            local_changes.append(card)
        if item.get("verification_status") == "context_corroborated":
            checks.append("Local 문맥 분류에는 규칙 기반 연결과 보조 본문 추출이 포함됩니다. 원문 게시일이 없으면 뉴스 제공일을 사용하며 사업 범위·실제 영향은 추가 확인이 필요합니다.")

    trend_patterns = []
    trend = valid.get("trend", {})
    product = request.get("campaign", {}).get("product", "")
    cases = {item.get("case_id"): item for item in trend.get("insights", []) if item.get("case_id")}
    patterns = trend.get("reference_patterns", trend.get("patterns", []))
    if not isinstance(patterns, list):
        checks.append("Trend 패턴 형식 오류를 확인하세요.")
        patterns = []
    for item in patterns:
        if not isinstance(item, dict):
            checks.append("Trend 패턴 형식 오류를 확인하세요.")
            continue
        raw_case_ids = item.get("example_case_ids", [])
        if not isinstance(raw_case_ids, list) or any(not isinstance(cid, str) for cid in raw_case_ids):
            checks.append("Trend 사례 참조 형식 오류를 확인하세요.")
            continue
        case_ids = list(dict.fromkeys(raw_case_ids))
        linked = [cases[cid] for cid in case_ids if cid in cases
                  and sources_for("trend", cases[cid].get("source_ids", []))
                  and len(sources_for("trend", cases[cid].get("source_ids", []))) == len(set(cases[cid]["source_ids"]))]
        sources = sources_for("trend", item.get("example_source_ids", []))
        linked_source_ids = {sid for case in linked for sid in case["source_ids"]}
        if (not linked or not sources or len(linked) != len(case_ids)
                or len(sources) != len(set(item.get("example_source_ids", [])))
                or any(source["source_id"] not in linked_source_ids for source in sources)):
            checks.append("Trend의 사례·출처 연결이 불완전한 패턴을 요약에서 제외했습니다.")
            continue
        card = deepcopy(item)
        groups = group_coverage(linked, product) if item.get("verification_status") == "candidate" else [[case] for case in linked]
        if item.get("verification_status") == "candidate" and len(groups) < 2:
            checks.append("Trend 관련 보도를 묶은 뒤 반복 패턴을 뒷받침할 서로 다른 후보 묶음이 부족해 패턴 요약에서 제외했습니다.")
            continue
        card.update(module="trend", evidence_count=len(groups), sources=sources,
                    article_count=len(linked), candidate_group_count=len(groups),
                    candidate_groups=[[case["case_id"] for case in group] for group in groups],
                    scope=("전국·다업종 검색 후보; 독립 행사·체험 구조·매장 응용 가설 확인 필요"
                           if item.get("verification_status") == "candidate" else "전국 체험 사례; 매장 응용 가설 검토"))
        trend_patterns.append(card)

    # Reference candidates are separate cards, never counted as repeated patterns.
    references = []
    for reference in trend.get("reference_cases", []):
        case = cases.get(reference.get("case_id"), {}) if isinstance(reference, dict) else {}
        if case.get("origin") != "live_search_candidate":
            continue
        ids = case.get("source_ids", [])
        sources = sources_for("trend", ids)
        if not sources or len(sources) != len(set(ids)):
            checks.append("Trend 참고 후보의 출처 연결을 확인하세요.")
            continue
        related_ids = reference.get('related_case_ids', [case.get('case_id')])
        if not isinstance(related_ids, list):
            related_ids = [case.get('case_id')]
        for cid in [case.get('case_id')] + related_ids:
            member = cases.get(cid)
            member_sources = sources_for('trend', member.get('source_ids', [])) if member else []
            if (member and member not in references and member.get('origin') == 'live_search_candidate'
                    and member_sources and len(member_sources) == len(set(member.get('source_ids', [])))
                    and member in group_coverage([case, member], product)[0]):
                references.append(member)
    for group in group_coverage(references, product):
        case = deepcopy(group[0])
        ids = list(dict.fromkeys(sid for member in group for sid in member.get("source_ids", [])))
        sources = sources_for("trend", ids)
        case["source_ids"] = ids
        case["context_source_refs"] = [ref for member in group for ref in member.get("context_source_refs", [])]
        case["why_relevant"] = list(dict.fromkeys(text for member in group for text in member.get("why_relevant", [])))
        case["limitations"] = list(dict.fromkeys(text for member in group for text in member.get("limitations", [])))
        card = deepcopy(case)
        card["article_count"] = len(group)
        card["grouped_case_ids"] = [member["case_id"] for member in group]
        card["supporting_facets"] = [{"case_id": member["case_id"], "title": member.get("event_name"),
                                      "observation": member.get("observation"), "source_ids": member["source_ids"]}
                                     for member in group[1:]]
        if len(group) > 1:
            card["limitations"].append("같은 날짜·브랜드·고유명 표현을 공유하는 관련 보도 묶음입니다. 동일 행사 여부는 원문 대조가 필요합니다.")
        context_sources = {}
        for ref in case.get("context_source_refs", []):
            if not isinstance(ref, dict) or ref.get("module") not in ("quant", "local"):
                continue
            module = ref["module"]
            linked = sources_for(module, [ref.get("source_id")])
            for source in linked:
                context_sources.setdefault(module, {})[source["source_id"]] = source
        expected = {(r.get("module"), r.get("source_id")) for r in case.get("context_source_refs", []) if isinstance(r, dict)}
        actual = {(module, sid) for module, entries in context_sources.items() for sid in entries}
        if expected != actual:
            # Keep the source-backed candidate, omit unsupported context reasoning.
            card["why_relevant"] = ["전국 체험 사례의 매장 응용 후보입니다. 맥락 근거 연결은 확인 필요합니다."]
            card.pop("audience_hypothesis", None)
            card.pop("adaptation_hypotheses", None)
            card.pop('audience_fit', None)
            checks.append("Trend 후보의 인구·지역 맥락 출처가 일부 누락되어 맥락 선정 이유를 제외했습니다.")
        card.update(module="trend", type="reference_case", sources=sources,
                    context_sources={m: list(entries.values()) for m, entries in context_sources.items()},
                    evidence_count=1, scope="검색 후보; 실제 행사·체험 구조·고객 적합성 미확인")
        if card.get('case_detail', {}).get('status') == 'text_corroborated':
            card['scope'] = '원문 제목·참여 방식 표현 대조; 실제 개최·고객 호응은 미확인'
        # Resolve fit provenance independently; do not publish unsupported cohort reasoning.
        card['audience_fit'] = [fit for fit in card.get('audience_fit', [])
            if isinstance(fit, dict) and fit.get('context_source_refs')
            and all((ref.get('module'), ref.get('source_id')) in actual
                    for ref in fit['context_source_refs'] if isinstance(ref, dict))
            and all(isinstance(ref, dict) for ref in fit['context_source_refs'])
            and fit.get('mechanism_source_ids')
            and fit.get('fit_status') == 'hypothesis_not_proven_preference'
            and set(fit['mechanism_source_ids']).issubset(set(ids))]
        trend_patterns.append(card)

    for item in trend.get('audience_contexts', []):
        if not isinstance(item, dict) or item.get('evidence_role') != 'audience_context':
            continue
        case = cases.get(item.get('case_id'), {})
        ids = case.get('source_ids', [])
        sources = sources_for('trend', ids)
        if sources and len(sources) == len(set(ids)):
            card = deepcopy(case)
            card.update(module='trend', type='audience_context', sources=sources,
                        scope='전국 고객층 조사 보도; 행사 사례·실제 방문 반응과 구분')
            trend_patterns.append(card)

    preview = evaluate_rules(bundle)
    checks.extend(preview["pending_checks"])
    for finding in preview["findings"]:
        if finding["level"] in ("needs_fix", "manual_review"):
            checks.append(f"{finding.get('module', '공통')}: {finding['message']}")
    if critic_result:
        checks.append(f"Graph Critic 상태: {critic_result.get('status', '미확인')}. 규칙 검사와 의미·사실 검토는 별개입니다.")
        checks.extend(str(warning) for warning in critic_result.get("warnings", []))
    checks.extend(["이 브리프는 근거 요약 초안이며 품질 최종 승인이 아닙니다.",
                   "지표의 기준 시점·지역 범위·집계 방법을 확인하세요. 매출 비중을 고객 수 비중으로 해석하지 마세요.",
                   "트렌드 패턴은 중복 사례를 포함하므로 패턴별 건수를 합산하지 마세요."])
    if sections.get("area"):
        checks.append("교통시설 원문 표의 시군구 기준 표기와 선택 영역 행의 범위를 확인하세요.")

    primary = None
    if demographics:
        primary = " / ".join(card["statement"] for card in demographics)
    elif facts:
        population_facts = [fact for fact in facts if fact["metric_refs"][0] in
                            ("daily_avg_floating_population", "resident_population", "worker_population")]
        if population_facts:
            primary = " / ".join(fact["statement"] for fact in population_facts)

    implications = []
    fact_by_metric = {fact["metric_refs"][0]: fact for fact in facts}
    if facts:
        implications.append({"statement": "상권·인구 수치를 함께 검토하되 자료 시점과 모집단을 구분해 조사 가설을 세우세요.",
                             "basis": deepcopy(facts), "kind": "research_question"})
    competition = fact_by_metric.get("telecom_store_count")
    change = fact_by_metric.get("telecom_store_yoy_percent")
    if competition and change:
        implications.append({"statement": f"핸드폰 소매업 {competition['value']:,}개, 전년동월 대비 {change['value']:g}%라는 관측을 바탕으로 경쟁 점포의 실제 영업 상태와 구성 변화를 확인하세요. 점포 수 변화만으로 경쟁 강도나 매출 기회를 확정할 수 없습니다.",
                             "basis": deepcopy([competition, change]), "kind": "research_question"})
    if demographics:
        implications.append({"statement": " / ".join(card["statement"] for card in demographics) + ". 생활·통근·통행 맥락을 구분해 제품 체험 수요를 추가 조사하세요. 인구 구성만으로 구매 고객을 정하지 않습니다.",
                             "basis": deepcopy(demographics), "kind": "research_question"})
    if local_changes:
        implications.append({"statement": "지역 변화의 사업 단계와 점포 생활권 관련성을 확인하세요. 계획·선정 발표를 현재 운영 또는 입주로 해석하지 마세요.",
                             "basis": deepcopy(local_changes), "kind": "research_question"})
    if local_context:
        implications.append({"statement": "주변 행정구역 변화와 지역 배경 자료를 조사 질문으로 활용하세요. 점포 생활권 연결과 영향 여부를 추가 확인하고 최근 지역 변화·고객 증가와 구분하세요.",
                             "basis": deepcopy(local_context), "kind": "research_question"})
    if trend_patterns:
        checks.append('Trend는 참여 방식과 응용 가능성의 조사 참고입니다. 고객 호응 자료는 선택적 보조 근거이며, 미확보만으로 사례를 제외하지 않습니다. 반복 등장하는 방식도 인기·성과를 입증하지 않습니다.')
        pattern_names = ", ".join(str(card.get("name") or card.get("event_name") or "체험 후보") for card in trend_patterns)
        campaign = request.get("campaign", {})
        product = campaign.get("product") or "요청 제품"
        implications.append({"statement": f"{pattern_names} 자료를 {product} 체험 목적과 대조해 적합성을 검토하세요. 방문 증가나 매출 효과는 이번 근거로 확정할 수 없습니다.",
                             "basis": deepcopy(trend_patterns), "kind": "research_question"})

    cards = facts + demographics + distributions + local_context + local_changes + trend_patterns
    urls = {source["source_url"] for card in cards for source in card.get("sources", [])}
    urls.update(source["source_url"] for card in cards for entries in card.get("context_sources", {}).values() for source in entries)
    store = request.get("store", {})
    address = store.get("address") or context.get("area_name") or "조사 지역 미확인"
    reference_count = sum(card.get("type") == "reference_case" for card in trend_patterns)
    audience_context_count = sum(card.get('type') == 'audience_context' for card in trend_patterns)
    area_summary = f"{address}: 정량 지표 {len(facts)}개, 직접 지역 변화 {len(local_changes)}건, 보조 맥락·배경 {len(local_context)}건, 체험 패턴 {len(trend_patterns)-reference_count-audience_context_count}개·참고 후보 {reference_count}건을 근거와 함께 요약했습니다. 자료 수는 독립 사건 수의 확정값이 아닙니다."
    if audience_context_count:
        area_summary += f' 전국 고객층 조사 맥락 {audience_context_count}건을 별도로 제공합니다.'
    if not cards:
        area_summary = f"{address}: 요약할 출처 연결 근거가 없습니다. 재수집 또는 자료 보완이 필요합니다."
    result = {"schema_version": "0.1", "request_id": request_id,
            "status": "manual_review" if cards else "failed",
            "overview": {"area_summary": area_summary, "primary_customer_signal": primary},
            "local_changes": local_changes, "unique_local_signals": facts + demographics + distributions + local_context,
            "trend_patterns": trend_patterns,
            "why_here_now": ("위 주소의 상권·인구 자료와 조회 기간의 생활권 변화, 체험 사례를 함께 검토할 수 있습니다. "
                             "지금 실행해야 할 이유나 다른 상권 대비 차별성은 근거의 시점·지역 관련성을 확인하기 전까지 확정하지 않습니다.") if cards else "근거 부족으로 why here / why now를 판단할 수 없습니다.",
            "research_implications": implications,
            "needs_manual_check": list(dict.fromkeys(checks)), "source_count": len(urls)}
    review = (critic_result or {}).get('checks', {}).get('semantic_review', {})
    if review.get('profile') == 'research':
        result['research_review'] = deepcopy(review)
        case_cards = {c['case_id']: c for c in trend_patterns if c.get('type') == 'reference_case'}
        result['research_review']['case_reviews'] = []
        for row in review.get('case_reviews', []):
            if row.get('case_id') in case_cards:
                card = case_cards[row['case_id']]
                result['research_review']['case_reviews'].append({**deepcopy(row), 'event_name': card.get('event_name'),
                    'source_ids': [s['source_id'] for s in card['sources']]})
    return result


def mock_brief(request_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "request_id": request_id,
        "status": "mock",
        "overview": {
            "area_summary": "SPOT mock Research Brief",
            "primary_customer_signal": None,
        },
        "local_changes": [],
        "unique_local_signals": [],
        "trend_patterns": [],
        "why_here_now": "Mock only. Real Scout evidence is not connected yet.",
        "research_implications": [],
        "needs_manual_check": ["Connect real Scout outputs before using this result."],
        "source_count": 0,
    }
