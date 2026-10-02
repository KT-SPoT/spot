"""Render the evidence draft as a readable Markdown report."""

from src.brief.generator import AGE_LABELS


def _cell(value):
    return str(value if value is not None else "확인 필요").replace("|", "\\|").replace("\n", " ")


def _refs(card):
    return ", ".join(f"{card.get('module', '?')}:{source['source_id']}"
                     for source in card.get("sources", [])) or "출처 확인 필요"


def _date_basis(card):
    return {"naver_provided_at": "뉴스 제공일(원문 게시일 미확인)",
            "article_published_at": "원문 게시일"}.get(card.get("date_basis"), "날짜 종류 확인 필요")


def render_markdown(brief):
    status = {"manual_review": "검토 필요", "failed": "근거 미확보"}.get(brief["status"], brief["status"])
    lines = ["# SPOT Research Brief", "", f"- 요청: {brief['request_id']}",
             f"- 상태: {status} — 조사 초안",
             f"- 인용한 고유 출처 URL: {brief['source_count']}개", "",
             brief["overview"]["area_summary"], "", "## 상권·인구 지표", ""]
    if any(c.get('evidence_basis') == 'public_agency_api' for c in brief['unique_local_signals']):
        lines.extend(['소상공인365 제공 관측값을 정량 기준으로 사용합니다. 성향·수요·효과에 관한 해석은 별도로 검토합니다.', ''])
    lines.extend(["| 항목 | 값 | 자료 기준 | 지역 범위 | 근거 |", "|---|---:|---|---|---|"])
    for card in brief["unique_local_signals"]:
        if "value" in card:
            raw = card['value']
            value = (format(raw, ',') if isinstance(raw, (int, float)) else str(raw)) + card['unit']
            lines.append("| " + " | ".join(map(_cell, (card["title"], value,
                         card.get("reference_period"), card.get("scope"), _refs(card)))) + " |")
    if not any("value" in card for card in brief["unique_local_signals"]):
        lines.append("| 자료 미확보 | — | 확인 필요 | 확인 필요 | — |")

    lines.extend(["", "## 성별·연령 구성", ""])
    demographic_cards = [card for card in brief["unique_local_signals"] if "shares" in card]
    if not demographic_cards:
        lines.append("성별·연령 비율을 확인할 원문 보조자료가 없습니다. 주요 성별·연령이라는 문구로 비율을 추정하지 않습니다.")
    for card in demographic_cards:
        lines.extend(["", f"### {card['title']}", "",
                      f"자료 기준: {_cell(card.get('reference_period'))} / {_cell(card['scope'])} / 근거: {_refs(card)}", "",
                      "| 구분 | 인구 | 비율 |", "|---|---:|---:|"])
        labels = {"male": "남성", "female": "여성", **AGE_LABELS}
        for key, label in labels.items():
            entry = card["shares"].get(key)
            if entry:
                count = entry.get("count")
                lines.append(f"| {label} | {format(count, ',') if isinstance(count, (int, float)) else '확인 필요'} | {entry['share_pct']:g}% |")
    signal = brief["overview"]["primary_customer_signal"]
    if signal:
        lines.extend(["", "주요 인구 신호: " + signal, "",
                      "유동·주거·직장 인구는 서로 다른 모집단입니다. 행사 고객을 확정하지 않습니다."])

    for role, heading in (("surrounding_context", "주변 행정구역 맥락"), ("background", "지역 배경 자료")):
        context_cards = [c for c in brief["unique_local_signals"] if c.get("evidence_role") == role]
        if not context_cards:
            continue
        lines.extend(["", "## " + heading, "", "아래 자료는 직접적인 최근 지역 변화 건수에 포함하지 않습니다."])
        for card in context_cards:
            lines.extend(["", f"### {card.get('title', heading)}", "", str(card.get("evidence") or "내용 확인 필요"), "",
                          f"- 자료 날짜: {_cell(card.get('published_at'))}; 날짜 종류: {_date_basis(card)}",
                          f"- 해석 범위: {card['scope']}", f"- 활용·한계: {_cell(card.get('context_note'))}",
                          f"- 근거: {_refs(card)}"])

    lines.extend(["", "## 최근 지역 변화", ""])
    if not brief["local_changes"]:
        lines.append("출처가 연결된 지역 변화 근거가 없습니다.")
    for card in brief["local_changes"]:
        stage = {"approved_plan": "계획 승인", "selected_future_project": "미래 사업 선정",
                 "scheduled": "계획·예정(완료 확인 아님)", "launched": "시작",
                 "reported_opening": "개관·운영 시작 보도(현장 미확인)",
                 "reported_plan_approval": "계획 변경·승인 보도(공사·운영 완료 아님)",
                 "not_applicable": "배경·주변 맥락",
                 "reported_construction_or_move_in": "공사·입주 단계 보도(현장 미확인)",
                 "unverified": "단계 확인 필요"}.get(card.get("change_state"), card.get("change_state"))
        lines.extend(["", f"### {card.get('title', '지역 변화')}", "",
                      str(card.get("evidence") or card.get("statement") or "내용 확인 필요"), "",
                      f"- 발표일: {_cell(card.get('published_at'))}",
                      f"- 사업 단계: {_cell(stage)}",
                      f"- 범위: {card['scope']}", f"- 근거: {_refs(card)}"])
        if card.get("article_checked"):
            label = "지역·변화 문장과 원문 게시일 대조" if card.get("verification_status") == "text_corroborated" else "원문 문맥에 따른 분류; 지역 연결·게시일은 추가 확인 가능"
            lines.append("- 확인 수준: " + label + "; 사건 발생 자체는 미검증")
            lines.append(f"- 날짜 종류: {_date_basis(card)}")
            if card.get("context_note"):
                lines.append("- 활용·한계: " + card["context_note"])
            for facet in card.get("supporting_facets", []):
                lines.append(f"- 관련 보도 {facet['source_id']}: {_cell(facet.get('evidence'))}")
        if card.get("why_it_matters"):
            lines.extend(["", "자료 해석(검토 필요): " + card["why_it_matters"]])

    lines.extend(["", "## 체험 트렌드 패턴", ""])
    if not brief["trend_patterns"]:
        lines.append("사례와 출처가 연결된 트렌드 패턴이 없습니다.")
    for card in brief["trend_patterns"]:
        if card.get("type") == "reference_case":
            lines.extend(["", f"### 참고 후보: {card.get('event_name', '체험 후보')}", "",
                          str(card.get("observation", "")), "",
                          f"- 선정 점수: {card.get('reference_priority_score')} (규칙 기반 비교값; 효과·품질 점수 아님)",
                          f"- 범위: {card['scope']}", f"- 근거: {_refs(card)}"])
            lines.extend("- 선정 이유: " + text for text in card.get("why_relevant", []))
            if card.get("audience_hypothesis"):
                lines.append("- 고객층 조사 가설: " + card["audience_hypothesis"])
            for hypothesis in card.get("adaptation_hypotheses", []):
                lines.append("- 매장 응용 가설: " + hypothesis["statement"])
            lines.extend("- 한계: " + text for text in card.get("limitations", []))
            if card.get("article_count", 1) > 1:
                lines.append(f"- 관련 보도: {card['article_count']}건을 후보 묶음 1개로 표시")
                for facet in card.get("supporting_facets", []):
                    lines.append(f"- 함께 묶은 보도: {_cell(facet.get('title'))}; 근거: {', '.join(facet['source_ids'])}")
            for module, entries in card.get("context_sources", {}).items():
                lines.append("- 맥락 근거: " + ", ".join(f"{module}:{s['source_id']}" for s in entries))
            continue
        label = "개 후보 묶음(독립 행사 미확인)" if card.get("verification_status") == "candidate" else "개 사례"
        lines.extend(["", f"### {card.get('name', '체험 패턴')} — {card['evidence_count']}{label}", "",
                      str(card.get("description", "")), "",
                      f"- 범위: {card['scope']}", f"- 근거: {_refs(card)}"])
        if card.get("verification_status") == "candidate":
            lines.append(f"- 연결된 보도: {card.get('article_count', card['evidence_count'])}건; 보도 묶음 간에도 동일 행사일 수 있어 원문 확인 필요")

    lines.extend(["", "## Why here / why now", "", brief["why_here_now"], "",
                  "## 기획 전 조사 질문", ""])
    for item in brief["research_implications"]:
        lines.append("- " + item["statement"])
    if not brief["research_implications"]:
        lines.append("근거를 먼저 보완해야 합니다.")
    lines.extend(["", "## 검토 필요 사항", ""])
    lines.extend("- " + str(item) for item in brief["needs_manual_check"])
    lines.extend(["", "## 출처", ""])
    sources = {}
    for card in brief["unique_local_signals"] + brief["local_changes"] + brief["trend_patterns"]:
        for source in card.get("sources", []):
            sources[(card["module"], source["source_id"])] = source
        for module, entries in card.get("context_sources", {}).items():
            for source in entries:
                sources[(module, source["source_id"])] = source
    for (module, source_id), source in sources.items():
        name = _cell(source.get("source_name") or source_id).replace("[", "\\[").replace("]", "\\]")
        url = source["source_url"].replace("(", "%28").replace(")", "%29")
        lines.append(f"- {module}:{source_id} — [{name}]({url}); 게시일: {_cell(source.get('published_at'))}; 수집일: {_cell(source.get('collected_at'))}")
    return "\n".join(lines) + "\n"
