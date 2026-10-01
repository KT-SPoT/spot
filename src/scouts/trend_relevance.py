"""Request-aware heuristics adapted from Trend PR #14 (bcfe647).

Pure functions only: no credentials, provider calls or automatic verification.
"""
import re
from typing import Any
from src.contracts import SpotRequest

REFERENCE_CASE_LIMIT = 5

MIN_RELEVANCE_SCORE = 5

STRONG_EXPERIENCE_KEYWORDS = (
    "팝업",
    "팝업스토어",
    "체험존",
    "체험공간",
    "직접 체험",
    "실물 체험",
    "부스",
    "전시",
    "쇼룸",
    "스탬프",
    "미션",
    "페스타",
    "페스티벌",
)

WEAK_EXPERIENCE_KEYWORDS = (
    "체험",
    "행사",
    "이벤트",
    "프로모션",
    "오프라인",
    "현장",
)

NEGATIVE_REVIEW_KEYWORDS = (
    "리뷰",
    "사용기",
    "후기",
    "장단점",
    "언박싱",
    "개봉기",
    "비교",
    "스펙",
    "꿀팁",
)

COMMERCE_KEYWORDS = (
    "가격",
    "구매",
    "사전예약",
    "쿠팡",
    "할인",
    "최저가",
)

def extract_region(address: str | None) -> str | None:
    """Return a broad Korean region name from a store address."""
    if not address:
        return None

    region_aliases = {
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "인천광역시": "인천",
        "광주광역시": "광주",
        "대전광역시": "대전",
        "울산광역시": "울산",
        "세종특별자치시": "세종",
        "경기도": "경기",
        "강원특별자치도": "강원",
        "충청북도": "충북",
        "충청남도": "충남",
        "전북특별자치도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주특별자치도": "제주",
    }

    for full_name, short_name in region_aliases.items():
        if full_name in address:
            return short_name

    first_token = address.strip().split()[0] if address.strip() else ""
    return first_token or None

def build_search_product_variants(product: str) -> list[str]:
    """Create readable search variants from the requested product name."""
    product = str(product or "").strip()

    if not product:
        return []

    variants = [product]

    korean_variant = (
        product
        .replace("Galaxy", "갤럭시")
        .replace("Fold", "폴드")
        .replace("Flip", "플립")
        .replace("Ultra", "울트라")
        .replace("iPhone", "아이폰")
    )

    if korean_variant != product:
        variants.append(korean_variant)

        # 국내 영상 제목에서 흔한 붙여쓰기 변형도 탐색한다.
        compact_korean = (
            korean_variant
            .replace(" Z 폴드", " Z폴드")
            .replace(" Z 플립", " Z플립")
        )
        if compact_korean != korean_variant:
            variants.append(compact_korean)

        no_z_variant = (
            korean_variant
            .replace(" Z 폴드", " 폴드")
            .replace(" Z 플립", " 플립")
        )
        if no_z_variant != korean_variant:
            variants.append(no_z_variant)

    return list(dict.fromkeys(variants))

def build_search_queries(request: SpotRequest) -> list[str]:
    """Build dynamic high-precision + recall YouTube queries."""

    campaign = request.get("campaign", {})
    store = request.get("store", {})

    product = str(campaign.get("product") or "").strip()
    purpose = str(campaign.get("purpose") or "").strip()
    store_name = str(store.get("name") or "").strip()
    region = extract_region(store.get("address"))

    brand_hint = store_name.split()[0] if store_name else ""
    product_variants = build_search_product_variants(product)

    queries: list[str] = []

    if product_variants:
        primary_product = product_variants[0]

        # 지역 기반 정밀 검색
        if region:
            queries.append(f"{primary_product} {region} 팝업")
            queries.append(f"{primary_product} {region} 체험")

        # 브랜드 + 제품 기반 검색
        if brand_hint:
            queries.append(f"{brand_hint} {primary_product} 체험")
            queries.append(f"{brand_hint} {primary_product} 체험공간")
            queries.append(f"{brand_hint} {primary_product} 행사")

        # 브랜드/지역 조건을 완화한 recall 검색
        queries.append(f"{primary_product} 팝업")
        queries.append(f"{primary_product} 체험공간")

        # 표기 변형별 탐색
        for variant in product_variants[1:]:
            if brand_hint:
                queries.append(f"{brand_hint} {variant} 체험")
                queries.append(f"{brand_hint} {variant} 체험공간")
            queries.append(f"{variant} 팝업")

    elif region and purpose:
        queries.append(f"{region} {purpose}")
        queries.append(f"{region} 체험형 마케팅 행사")

    if not queries:
        queries.append("체험형 마케팅 팝업 이벤트")

    return list(dict.fromkeys(queries))

def normalize_text(value: Any) -> str:
    """Normalize free text for deterministic keyword scoring."""
    return " ".join(str(value or "").lower().split())

def get_brand_hint(request: SpotRequest) -> str:
    """Use the first token of store name as a lightweight brand hint."""
    store = request.get("store", {})
    store_name = str(store.get("name") or "").strip()

    if re.match(r"(?i)^KT(?:\s|플라자|plaza|$)", store_name):
        return "KT"
    return store_name.split()[0] if store_name else ""

def contains_brand_term(text: str, brand: str) -> bool:
    """Match an ASCII brand as a token so KT does not match SKT."""
    normalized_brand = normalize_text(brand)

    if not normalized_brand:
        return False

    if normalized_brand.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_brand)}(?![a-z0-9])"
        return re.search(pattern, text) is not None

    return normalized_brand in text

def build_product_terms(product: str) -> list[str]:
    """Build simple Korean/English aliases for product matching."""
    raw = normalize_text(product)

    if not raw:
        return []

    terms = [raw]

    substitutions = {
        "galaxy": "갤럭시",
        "fold": "폴드",
        "flip": "플립",
        "ultra": "울트라",
        "iphone": "아이폰",
    }

    translated = raw
    for source, target in substitutions.items():
        translated = translated.replace(source, target)

    if translated != raw:
        terms.append(translated)

    # 공백을 제거한 형태도 함께 비교한다.
    compact_terms = [term.replace(" ", "") for term in terms]
    terms.extend(compact_terms)

    return list(dict.fromkeys(term for term in terms if term))

def build_product_match_terms(
    product: str,
) -> dict[str, list[str]]:
    """Build exact-model and product-family aliases from request.product.

    The returned terms are generated from the request value rather than
    hard-coded to one campaign.  Some morphology rules are intentionally
    domain-specific for common smartphone naming conventions.
    """
    raw = normalize_text(product)

    if not raw:
        return {
            "exact": [],
            "family": [],
        }

    exact_terms = build_product_terms(product)
    family_terms: list[str] = []

    # 모델 코어 토큰 보강:
    # Galaxy Z Fold8 -> fold8 / 폴드8 / z fold8 / z폴드8
    fold_or_flip = re.search(
        r"(fold|flip)\s*([0-9]+)",
        raw,
    )

    if fold_or_flip:
        model_name = fold_or_flip.group(1)
        model_number = fold_or_flip.group(2)
        korean_model = (
            "폴드"
            if model_name == "fold"
            else "플립"
        )

        exact_terms.extend(
            [
                f"{model_name}{model_number}",
                f"{model_name} {model_number}",
                f"{korean_model}{model_number}",
                f"{korean_model} {model_number}",
                f"z {model_name}{model_number}",
                f"z{model_name}{model_number}",
                f"z {korean_model}{model_number}",
                f"z{korean_model}{model_number}",
            ]
        )

        # 요청한 모델을 직접 적지 않고 같은 출시 제품군으로
        # 표현하는 국내 콘텐츠를 family 수준으로 인식한다.
        family_terms.extend(
            [
                "galaxy z series",
                "galaxy z new",
                "갤럭시 z 시리즈",
                "갤럭시 z 신제품",
                f"foldable {model_number}",
                f"foldable{model_number}",
                f"폴더블 {model_number}",
                f"폴더블{model_number}",
            ]
        )

    # iPhone 18 -> iPhone 18 / 아이폰18은 exact,
    # "아이폰 18 시리즈", "아이폰 신제품"은 family.
    iphone_match = re.search(
        r"iphone\s*([0-9]+)",
        raw,
    )

    if iphone_match:
        model_number = iphone_match.group(1)

        exact_terms.extend(
            [
                f"iphone {model_number}",
                f"iphone{model_number}",
                f"아이폰 {model_number}",
                f"아이폰{model_number}",
            ]
        )

        family_terms.extend(
            [
                f"iphone {model_number} series",
                f"iphone{model_number} series",
                f"아이폰 {model_number} 시리즈",
                f"아이폰{model_number} 시리즈",
                "iphone 신제품",
                "아이폰 신제품",
            ]
        )

    def clean_terms(values: list[str]) -> list[str]:
        normalized: list[str] = []

        for value in values:
            term = normalize_text(value)

            if not term:
                continue

            normalized.append(term)
            normalized.append(term.replace(" ", ""))

        return list(dict.fromkeys(normalized))

    return {
        "exact": clean_terms(exact_terms),
        "family": clean_terms(family_terms),
    }

def find_product_match(
    combined: str,
    compact_combined: str,
    product: str,
) -> tuple[str, str | None]:
    """Return (exact|family|none, matched_term)."""
    terms = build_product_match_terms(product)

    def matches(term):
        # Fold8 must not silently become Fold80 (likewise iPhone18/180).
        suffix = r"(?![0-9])" if term[-1:].isdigit() else ""
        return any(re.search(re.escape(term) + suffix, text) for text in (combined, compact_combined))

    for term in terms["exact"]:
        if matches(term):
            return "exact", term

    for term in terms["family"]:
        if matches(term):
            return "family", term

    return "none", None

def contains_experience_keyword(
    keyword: str,
    combined: str,
    compact_combined: str,
) -> bool:
    """Match experience keywords while avoiding known lexical false positives."""
    normalized_keyword = normalize_text(keyword)
    compact_keyword = normalized_keyword.replace(" ", "")

    # "타임 스탬프"의 스탬프는 미션형 체험이 아니다.
    if normalized_keyword == "스탬프":
        if (
            "타임 스탬프" in combined
            or "타임스탬프" in compact_combined
        ):
            return False

    return (
        normalized_keyword in combined
        or compact_keyword in compact_combined
    )

def score_candidate_relevance(
    candidate: dict[str, Any],
    request: SpotRequest,
) -> dict[str, Any]:
    """Attach an explainable relevance score to one YouTube candidate."""
    title = normalize_text(candidate.get("title"))
    description = normalize_text(candidate.get("description"))
    channel_title = normalize_text(candidate.get("channel_title"))
    combined = f"{title} {description} {channel_title}"
    compact_combined = combined.replace(" ", "")

    campaign = request.get("campaign", {})
    store = request.get("store", {})

    product = str(campaign.get("product") or "").strip()
    region = extract_region(store.get("address"))
    brand_hint = get_brand_hint(request)

    score = 0
    reasons: list[str] = []

    # 1) 제품 관련성
    # exact: 요청 모델이 직접 등장
    # family: 동일 출시 제품군/제품군 표현이 등장
    # none: 요청 제품과 연결되는 표현이 없음
    product_match_level, product_match_term = find_product_match(
        combined,
        compact_combined,
        product,
    )

    exact_product_match = product_match_level == "exact"
    family_product_match = product_match_level == "family"
    product_match = product_match_level != "none"

    if exact_product_match:
        score += 4
        reasons.append("PRODUCT_MATCH")
        reasons.append(
            f"EXACT_PRODUCT_MATCH:{product_match_term}"
        )
    elif family_product_match:
        score += 2
        reasons.append(
            f"FAMILY_PRODUCT_MATCH:{product_match_term}"
        )

    # 2) 매장/브랜드 관련성
    brand_match = bool(
        brand_hint
        and contains_brand_term(
            combined,
            brand_hint,
        )
    )

    if brand_match:
        score += 2
        reasons.append("BRAND_MATCH")

    # 3) 지역 관련성
    if region and normalize_text(region) in combined:
        score += 3
        reasons.append("LOCATION_MATCH")

    # 4) 체험형 마케팅 키워드
    # 강한 키워드(팝업/체험존/오프라인/현장 등)는 큰 가산점,
    # 약한 키워드(체험/행사/이벤트/프로모션)는 작은 가산점만 준다.
    strong_experience_hits = [
        keyword
        for keyword in STRONG_EXPERIENCE_KEYWORDS
        if contains_experience_keyword(
            keyword,
            combined,
            compact_combined,
        )
    ]

    weak_experience_hits = [
        keyword
        for keyword in WEAK_EXPERIENCE_KEYWORDS
        if contains_experience_keyword(
            keyword,
            combined,
            compact_combined,
        )
    ]

    if strong_experience_hits:
        strong_score = min(len(strong_experience_hits) * 3, 6)
        score += strong_score
        reasons.extend(
            f"STRONG_EXPERIENCE_KEYWORD:{keyword}"
            for keyword in strong_experience_hits
        )

    if weak_experience_hits:
        weak_score = min(len(weak_experience_hits), 3)
        score += weak_score
        reasons.extend(
            f"WEAK_EXPERIENCE_KEYWORD:{keyword}"
            for keyword in weak_experience_hits
        )

    # 5) 여러 검색어에서 반복 노출된 영상은 약한 가산점
    matched_query_count = len(candidate.get("matched_queries") or [])

    if matched_query_count >= 2:
        score += min(matched_query_count - 1, 2)
        reasons.append(
            f"MULTI_QUERY_MATCH:{matched_query_count}"
        )

    # 6) 일반 리뷰/사용기 성격은 강한 감점
    review_hits = [
        keyword
        for keyword in NEGATIVE_REVIEW_KEYWORDS
        if keyword in combined
    ]

    if review_hits:
        review_penalty = min(len(review_hits) * 3, 9)
        score -= review_penalty
        reasons.extend(
            f"REVIEW_KEYWORD:{keyword}"
            for keyword in review_hits
        )

    # 7) 구매/가격 중심 영상도 감점
    commerce_hits = [
        keyword
        for keyword in COMMERCE_KEYWORDS
        if keyword in combined
    ]

    if commerce_hits:
        commerce_penalty = min(len(commerce_hits) * 2, 6)
        score -= commerce_penalty
        reasons.extend(
            f"COMMERCE_KEYWORD:{keyword}"
            for keyword in commerce_hits
        )

    enriched = dict(candidate)
    enriched["relevance_score"] = score
    enriched["relevance_reasons"] = reasons
    enriched["strong_experience_keyword_hits"] = strong_experience_hits
    enriched["weak_experience_keyword_hits"] = weak_experience_hits
    enriched["experience_keyword_hits"] = (
        strong_experience_hits + weak_experience_hits
    )
    enriched["review_keyword_hits"] = review_hits
    enriched["commerce_keyword_hits"] = commerce_hits

    # 기존 bool 필드는 하위 호환을 위해 유지한다.
    enriched["product_match"] = product_match
    enriched["product_match_level"] = product_match_level
    enriched["product_match_term"] = product_match_term
    enriched["exact_product_match"] = exact_product_match
    enriched["family_product_match"] = family_product_match
    enriched["brand_match"] = brand_match

    # "애플 이벤트"처럼 약한 키워드 하나만 있는 경우는 제외한다.
    # 다음 중 하나를 만족해야 체험형 구조로 본다.
    # 1) 강한 공간/체험 키워드가 1개 이상
    # 2) 약한 체험 키워드가 서로 다른 2개 이상 함께 등장
    has_experiential_structure = (
        bool(strong_experience_hits)
        or len(set(weak_experience_hits)) >= 2
    )

    # 제품명이 주어진 요청:
    # - exact match는 체험 구조가 확인되면 통과 가능
    # - family match는 오탐 방지를 위해 같은 브랜드까지 확인
    # 제품명이 없는 요청은 기존 체험형 구조 판정을 유지한다.
    if not product:
        product_requirement_met = True
    elif exact_product_match:
        product_requirement_met = True
    elif family_product_match and brand_match:
        product_requirement_met = True
    else:
        product_requirement_met = False

    enriched["product_requirement_met"] = (
        product_requirement_met
    )

    enriched["is_experiential_candidate"] = (
        score >= MIN_RELEVANCE_SCORE
        and has_experiential_structure
        and product_requirement_met
    )

    return enriched


def build_case_reference_score(
    case: dict[str, Any],
    request: SpotRequest,
) -> tuple[int, list[str]]:
    """Build transparent heuristic signals for reference-case ordering.

    This is NOT a final automatic relevance judgement.
    It only orders already-verified cases so that the Trend Scout can
    present a smaller reference set for the current campaign request.
    """
    campaign = request.get("campaign", {})
    store = request.get("store", {})

    purpose = normalize_text(campaign.get("purpose"))
    product = str(campaign.get("product") or "").strip()
    brand_hint = get_brand_hint(request)
    region = extract_region(store.get("address"))

    case_text = normalize_text(
        " ".join(
            [
                str(case.get("brand") or ""),
                str(case.get("event_name") or ""),
                str(case.get("observation") or ""),
                str(case.get("evidence_summary") or ""),
                str(case.get("location") or ""),
            ]
        )
    )
    compact_case_text = case_text.replace(" ", "")

    score = 0
    signals: list[str] = []

    # 요청 제품 또는 제품군과 사례 본문이 직접 맞닿는 경우
    product_terms = build_product_terms(product)

    product_tokens = [
        token
        for token in re.findall(r"[a-z가-힣]+\d+", normalize_text(product))
        if len(token) >= 3
    ]

    translated_product_tokens = []
    for token in product_tokens:
        translated = (
            token
            .replace("fold", "폴드")
            .replace("flip", "플립")
            .replace("ultra", "울트라")
            .replace("iphone", "아이폰")
        )
        translated_product_tokens.append(translated)

    family_terms = list(
        dict.fromkeys(
            product_terms
            + product_tokens
            + translated_product_tokens
        )
    )

    if product and any(
        term in case_text or term in compact_case_text
        for term in family_terms
    ):
        score += 5
        signals.append("PRODUCT_OR_FAMILY_MATCH")

    # 요청 매장의 브랜드와 사례 브랜드가 직접 연결되는 경우
    if brand_hint and contains_brand_term(case_text, brand_hint):
        score += 4
        signals.append("SAME_BRAND")

    # 같은 광역 지역에서 열린 사례는 지역 적용성 참고 신호로 사용
    if region and normalize_text(region) in normalize_text(case.get("location")):
        score += 2
        signals.append("SAME_REGION")

    tags = set(case.get("taxonomy_tags") or [])

    # 신제품 체험 목적에는 직접 사용/조작형 사례를 우선
    if "direct_product_trial" in tags:
        if "체험" in purpose or product:
            score += 4
            signals.append("DIRECT_PRODUCT_TRIAL_FIT")
        else:
            score += 2
            signals.append("DIRECT_PRODUCT_TRIAL_PATTERN")

    # 행사/체험/프로모션 목적에는 미션형 동선도 참고 가치가 있음
    if (
        "mission_journey" in tags
        and any(
            keyword in purpose
            for keyword in ("체험", "행사", "이벤트", "프로모션")
        )
    ):
        score += 2
        signals.append("MISSION_JOURNEY_FIT")

    # 공간 연출 참고용 보조 신호
    if (
        "worldbuilding_exploration" in tags
        and any(
            keyword in purpose
            for keyword in ("체험", "행사", "팝업", "브랜드")
        )
    ):
        score += 1
        signals.append("SPACE_EXPERIENCE_FIT")

    return score, signals


def select_reference_cases(
    cases: list[dict[str, Any]],
    request: SpotRequest,
    limit: int = REFERENCE_CASE_LIMIT,
) -> list[dict[str, Any]]:
    """Select a small reference set from verified cases.

    The score is a transparent ordering heuristic only.
    It must not be interpreted as an automatic final relevance judgement.
    """
    ranked: list[dict[str, Any]] = []

    for case in cases:
        score, signals = build_case_reference_score(case, request)

        enriched = dict(case)
        enriched["_reference_score"] = score
        enriched["_fit_signals"] = signals
        ranked.append(enriched)

    ranked.sort(
        key=lambda item: (
            -int(item.get("_reference_score", 0)),
            item.get("case_id") or "",
        )
    )

    return ranked[:limit]
