"""Request-scoped Local discovery; search passages require human verification."""
import re
from src.scouts import search_runtime as search
from src.scouts.local_evidence import verify_source
from datetime import date

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
    output["query_context"].update(verification_policy="article_text_check", verification_log=[])
    output["warnings"] = ["RADIUS_NOT_VERIFIED",
                           "원문 대조는 보도 내용의 확인이며 실제 사건·점포 반경을 검증하지 않습니다.",
                           "NAVER_DATE_IS_PROVIDED_AT", "DISTINCT_ARTICLES_MAY_DESCRIBE_SAME_EVENT",
                           "BOUNDED_SEARCH_NOT_EXHAUSTIVE"]
    if not anchor:
        output["errors"].append({"code": "MISSING_LOCATION_CONTEXT"})
        return output
    seen = set()
    checked = 0
    for query in (anchor, anchor + " 개관 개통 입주"):
        for item in search.collect(output, search.news, query, start, end):
            text = item["title"] + " " + item["description"]
            if search.normalized(anchor) not in search.normalized(text) or not any(w in text for w in CHANGE_WORDS):
                continue
            if item["source_url"] in seen or checked >= 15:
                continue
            seen.add(item["source_url"])
            checked += 1
            verification = verify_source(item, anchor, start, end)
            output["query_context"]["verification_log"].append({"source_url": item["source_url"],
                "status": verification["status"], "reason": verification.get("reason")})
            if verification["status"] == "rejected":
                continue
            number = len(output["sources"]) + 1
            sid = f"S-L-{number:03}"
            source = dict(item, source_id=sid, verification=verification)
            if verification.get("article_published_at"):
                source.update(published_at=verification["article_published_at"],
                              provider_published_at=item["published_at"], date_basis="article_published_at")
            output["sources"].append(source)
            fingerprint = verification.get("evidence_fingerprint")
            duplicate = next((i for i in output["insights"]
                if verification["status"] == "text_corroborated" and i.get("verification_status") == "text_corroborated"
                and i.get("evidence_fingerprint") == fingerprint and i["change_state"] == verification.get("change_state")
                and abs((date.fromisoformat(i["published_at"][:10]) - date.fromisoformat(source["published_at"][:10])).days) <= 7), None)
            if duplicate:
                duplicate["source_ids"].append(sid)
                duplicate["duplicate_basis"] = "identical_region_change_sentence_within_7_days"
                continue
            output["insights"].append({"insight_id": f"L-{number:03}", "type": "local_change_candidate",
                "title": item["title"], "evidence": verification.get("excerpt") or item["description"], "published_at": source["published_at"],
                "change_state": verification.get("change_state", "unverified"),
                "article_checked": True, "evidence_fingerprint": fingerprint,
                "evidence_basis": "article_text" if verification.get("excerpt") else "search_passage",
                "locality_tags": [anchor], "source_ids": [sid], "verification_status": verification["status"]})
    output["status"] = "partial" if output["insights"] else "failed"
    corroborated = sum(i["verification_status"] == "text_corroborated" for i in output["insights"])
    output["summary"] = f"{anchor}: 원문·게시일 대조 {corroborated}건, 나머지 미확인 후보 {len(output['insights']) - corroborated}건. 실제 사건·반경은 별도 검토 필요."
    output["finished_at"] = search.now()
    return output
