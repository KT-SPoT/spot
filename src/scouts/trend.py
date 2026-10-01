"""Live news and YouTube metadata discovery, without claiming event verification."""
from src.scouts import search_runtime as search

PATTERNS = {
    "mission_journey": ("미션 기반 참여 동선", ("미션", "스탬프", "단서")),
    "direct_product_trial": ("직접 제품·기능 체험", ("체험", "시연", "hands-on")),
    "worldbuilding_exploration": ("세계관·테마 공간 탐색", ("세계관", "테마 공간", "테마존")),
}
OFFLINE_CUES = ("팝업", "체험존", "체험 공간", "체험공간", "오프라인 행사", "전시회", "전시관", "행사장", "체험관")


def product_alias(product):
    alias = product
    for old, new in (("galaxy", "갤럭시"), ("fold", "폴드"), ("flip", "플립"), ("iphone", "아이폰")):
        alias = alias.lower().replace(old, new)
    return alias


def run_trend_scout(request):
    output = search.result(request, "trend")
    output["patterns"] = []
    try:
        start, end, days = search.window(request)
    except (ValueError, TypeError):
        output["errors"].append({"code": "INVALID_RESEARCH_WINDOW"})
        return output
    campaign = request.get("campaign") or {}
    product = campaign.get("product") or ""
    if not isinstance(product, str) or not product.strip():
        output["errors"].append({"code": "MISSING_CAMPAIGN_PRODUCT"})
        return output
    alias = product_alias(product)
    category = "스마트폰" if any(w in product.lower() for w in ("galaxy", "iphone", "갤럭시", "아이폰", "스마트폰")) else None
    queries = [alias + " 팝업 체험"]
    if category:
        queries.append(category + " 팝업 체험")
    output["query_context"].update(reference_date=end.isoformat(), lookback_start=start.isoformat(),
        lookback_days=days, product=product, scope="제품 및 인접 카테고리 후보; 행사 지역 미확인")
    output["warnings"] = ["SEARCH_METADATA_ONLY_EVENTS_UNVERIFIED", "YOUTUBE_CONTENT_NOT_WATCHED",
        "후보자료 수는 독립 행사 수가 아닙니다. 원문·영상·실제 체험 구조 확인이 필요합니다.",
        "NAVER_DATE_IS_PROVIDED_AT", "DISTINCT_SOURCES_NOT_DISTINCT_EVENTS", "BOUNDED_SEARCH_NOT_EXHAUSTIVE"]
    seen = set()
    for provider in (search.news, search.videos):
        for query in queries:
            for item in search.collect(output, provider, query, start, end):
                text = item["title"] + " " + item["description"]
                # A news passage can include unrelated navigation/related-story text.
                # Require product/category relevance in the headline itself.
                normalized = search.normalized(item["title"])
                same_product = any(search.normalized(p) in normalized for p in (product, alias))
                category_related = category and any(w in item["title"].lower() for w in ("스마트폰", "갤럭시", "아이폰", "galaxy", "iphone"))
                # News must foreground the event, not just mention a store in a sales story.
                cue_text = item["title"] if item["source_type"] == "news" else text
                if not (same_product or category_related) or not any(w in cue_text.lower() for w in OFFLINE_CUES):
                    continue
                provider_count = sum(s["source_type"] == item["source_type"] for s in output["sources"])
                if item["source_url"] in seen or provider_count >= 10:
                    continue
                seen.add(item["source_url"])
                number = len(output["sources"]) + 1
                sid, cid = f"S-T-{number:03}", f"T-{number:03}"
                tags = [key for key, (_, words) in PATTERNS.items() if any(w in text.lower() for w in words)]
                output["sources"].append(dict(item, source_id=sid, verification={"method": "search_metadata", "event_verified": False}))
                output["insights"].append({"case_id": cid, "type": "experiential_marketing_candidate",
                    "event_name": item["title"], "observation": item["description"],
                    "published_at": item["published_at"], "brand": None, "location": None,
                    "source_ids": [sid], "taxonomy_tags": tags, "verification_status": "candidate",
                    "request_relevance": "same_product" if same_product else "adjacent_category"})
    for key, (name, _) in PATTERNS.items():
        cases = [i for i in output["insights"] if key in i["taxonomy_tags"]]
        if len(cases) >= 2:
            output["patterns"].append({"pattern_id": key, "name": name,
                "description": "검색 메타데이터에서 관련 표현이 반복됨. 실제 경험 구조와 독립 행사 여부는 확인 필요.",
                "evidence_basis": "search_metadata", "verification_status": "candidate",
                "evidence_count": len(cases),
                "example_case_ids": [i["case_id"] for i in cases],
                "example_source_ids": [s for i in cases for s in i["source_ids"]]})
    output["status"] = "partial" if output["insights"] else "failed"
    output["summary"] = f"제품·카테고리 관련 체험 후보자료 {len(output['insights'])}건을 실제 수집. 원문·영상 확인 필요."
    output["finished_at"] = search.now()
    return output
