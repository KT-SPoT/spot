"""Request-scoped Local discovery; search passages require human verification."""
import re
from src.scouts import search_runtime as search

CHANGE_WORDS = ("개관", "개통", "입주", "착공", "준공", "신설", "오픈", "건립", "확충", "공사", "계획", "승인")


def area_anchor(store):
    name = store.get("name") or ""
    match = re.search(r"([가-힣]+신도시)", name)
    if match:
        return match.group(1)
    address = store.get("address") or ""
    match = re.search(r"(?:^|\s)([가-힣]+(?:동|읍|면))(?:\s|$)", address)
    if match:
        return match.group(1)
    match = re.search(r"(?:^|\s)([가-힣]+)\d*(?:로|길)(?:\s|\d)", address)
    if match:
        return match.group(1)
    return None


def run_local_scout(request):
    output = search.result(request, "local")
    try:
        start, end, days = search.window(request)
    except (ValueError, TypeError):
        output["errors"].append({"code": "INVALID_RESEARCH_WINDOW"})
        return output
    anchor = area_anchor(request.get("store") or {})
    output["query_context"].update(area_anchor=anchor, reference_date=end.isoformat(),
        lookback_start=start.isoformat(), lookback_days=days, scope="요청 지역명 일치; 점포 반경 미검증",
        requested_store=request.get("store") or {})
    output["warnings"] = ["SEARCH_PASSAGES_ONLY_FULL_TEXT_UNVERIFIED", "RADIUS_NOT_VERIFIED",
                           "지역명은 일치하지만 기사 원문·반경 내 실제 위치·변화 단계는 미검증입니다.",
                           "NAVER_DATE_IS_PROVIDED_AT", "DISTINCT_ARTICLES_MAY_DESCRIBE_SAME_EVENT",
                           "BOUNDED_SEARCH_NOT_EXHAUSTIVE"]
    if not anchor:
        output["errors"].append({"code": "MISSING_LOCATION_CONTEXT"})
        return output
    seen = set()
    for query in (anchor, anchor + " 개관 개통 입주"):
        for item in search.collect(output, search.news, query, start, end):
            text = item["title"] + " " + item["description"]
            if search.normalized(anchor) not in search.normalized(text) or not any(w in text for w in CHANGE_WORDS):
                continue
            if item["source_url"] in seen or len(output["insights"]) >= 15:
                continue
            seen.add(item["source_url"])
            number = len(output["sources"]) + 1
            sid = f"S-L-{number:03}"
            source = dict(item, source_id=sid, verification={"method": "search_passage", "full_text_verified": False})
            output["sources"].append(source)
            output["insights"].append({"insight_id": f"L-{number:03}", "type": "local_change_candidate",
                "title": item["title"], "evidence": item["description"], "published_at": item["published_at"],
                "change_state": "scheduled" if any(w in text for w in ("예정", "계획", "목표")) else "unverified",
                "locality_tags": [anchor], "source_ids": [sid], "verification_status": "candidate"})
    output["status"] = "partial" if output["insights"] else "failed"
    output["summary"] = f"{anchor}: 지역명·조회기간이 맞는 변화 후보자료 {len(output['insights'])}건. 원문과 실제 위치 확인 필요."
    output["finished_at"] = search.now()
    return output
