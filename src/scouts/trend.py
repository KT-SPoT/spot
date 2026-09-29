"""Trend Scout — owner: 김건희.

Week-1 implementation:
- Use a curated pool of verified experiential-marketing cases.
- Filter cases using SpotRequest.research reference_date / lookback_days.
- Extract repeated experience patterns using deterministic rules.
- Return ScoutResult v0.1.

YouTube discovery itself remains outside the runtime path.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

from src.contracts import ScoutResult, SpotRequest


# =========================================================
# 1. 기본 설정
# =========================================================

KST = timezone(timedelta(hours=9))

MIN_CONFIRMED_CASES = 5
MIN_PATTERN_EVIDENCE = 2


# =========================================================
# 2. 패턴 정의
# =========================================================

PATTERN_DEFINITIONS = {
    "mission_journey": {
        "name": "미션 기반 참여 동선",
        "description": (
            "방문자가 단서, 미션, 스탬프 등의 과제를 수행하며 "
            "공간을 순차적으로 이동하도록 설계하는 경험 구조"
        ),
    },
    "direct_product_trial": {
        "name": "직접 제품·기능 체험",
        "description": (
            "제품이나 핵심 기능을 설명으로 보여주는 데 그치지 않고 "
            "방문자가 직접 사용·착용·조작하게 하는 경험 구조"
        ),
    },
    "worldbuilding_exploration": {
        "name": "세계관·테마 공간 탐색",
        "description": (
            "브랜드나 IP의 세계관을 오프라인 공간으로 구현하고 "
            "방문자가 그 공간을 탐색하도록 만드는 경험 구조"
        ),
    },
}


# =========================================================
# 3. 검증 완료 사례 Pool
# =========================================================

VERIFIED_CASES: list[dict[str, Any]] = [
    {
        "case_id": "T-001",
        "brand": "Hermès",
        "event_name": "Mystery at the Grooms'",
        "published_at": "2026-06-08",
        "location": "서울 DDP",
        "youtube_url": "https://www.youtube.com/watch?v=4JsAObYs6iM",
        "verification_url": (
            "https://www.hermes.com/kr/ko/content/"
            "401129-mystery-at-the-grooms-kr/"
        ),
        "verification_source_type": "official_web",
        "observation": (
            "방문자가 에르메스의 탐정 역할을 맡아 공간에 흩어진 "
            "단서를 따라 제한 시간 내 숨은 말을 찾는다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "worldbuilding_exploration",
        ],
    },
    {
        "case_id": "T-002",
        "brand": "현대자동차",
        "event_name": "Youth Adventure 2026",
        "published_at": "2026-06-01",
        "location": "현대 모터스튜디오 부산",
        "youtube_url": "https://www.youtube.com/watch?v=qOcUFhwaKkY",
        "verification_url": (
            "https://motorstudio.hyundai.com/busan/cotn/exhb/"
            "youthAdventure.do?strgCd=04"
        ),
        "verification_source_type": "official_web",
        "observation": (
            "캐치! 티니핑 IP를 활용한 공간에서 방문자가 "
            "수소 에너지와 차량 관련 콘텐츠를 체험하고 "
            "게임존 형태의 프로그램에 참여한다."
        ),
        "taxonomy_tags": [
            "direct_product_trial",
            "worldbuilding_exploration",
        ],
    },
    {
        "case_id": "T-003",
        "brand": "KT",
        "event_name": "Galaxy Z Flip8·Fold8 체험공간",
        "published_at": "2026-07-24",
        "location": "전국 KT 주요 매장",
        "youtube_url": "https://www.youtube.com/watch?v=aJjrC8FII8g",
        "verification_url": (
            "https://www.sentv.co.kr/article/view/"
            "sentv202607240038"
        ),
        "verification_source_type": "news",
        "observation": (
            "방문자가 Galaxy Z Flip8·Fold8의 주요 기능을 직접 "
            "사용하며 미션을 수행하고 완료 단계에 따라 "
            "기념품을 받는다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "direct_product_trial",
        ],
    },
    {
        "case_id": "T-004",
        "brand": "Roblox × MUSINSA",
        "event_name": "MY LIFE WITH ROBLOX 2026",
        "published_at": "2026-07-27",
        "location": "서울 성수",
        "youtube_url": "https://www.youtube.com/watch?v=ClSmrCm869I",
        "verification_url": (
            "https://m.musinsa.com/content/"
            "1528923777154874918"
        ),
        "verification_source_type": "official_web",
        "observation": (
            "방문자가 성수의 무신사 공간과 Roblox 세계를 "
            "연결해 탐험하고 미니게임과 보물찾기 콘텐츠에 "
            "참여한다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "worldbuilding_exploration",
        ],
    },
    {
        "case_id": "T-005",
        "brand": "신일전자",
        "event_name": "신일 바람 정거장",
        "published_at": "2026-09-08",
        "location": "서울시청 광장",
        "youtube_url": "https://www.youtube.com/watch?v=PC2DGzZPjiY",
        "verification_url": (
            "https://www.shinil.co.kr/ko/press/"
            "press.html?b_no=131&mode=VIEW_FORM"
        ),
        "verification_source_type": "official_web",
        "observation": (
            "방문자가 신일의 생활가전을 직접 살펴보고 경험하며 "
            "추억의 뽑기 이벤트에 참여해 쿠폰과 굿즈를 받는다."
        ),
        "taxonomy_tags": [
            "direct_product_trial",
        ],
    },
    {
        "case_id": "T-006",
        "brand": "Dyson",
        "event_name": "Supersonic Travel Lounge",
        "published_at": "2026-04-23",
        "location": "서울 성수",
        "youtube_url": "https://www.youtube.com/watch?v=XVQrSzl2uls",
        "verification_url": (
            "https://www.asiae.co.kr/article/"
            "enterprise-CEO/2026042316120439640"
        ),
        "verification_source_type": "news",
        "observation": (
            "방문자가 여권과 항공권을 받고 여행지를 선택한 뒤 "
            "공항 콘셉트 공간을 이동하며 스탬프 미션을 수행하고 "
            "Supersonic Travel 제품을 직접 체험한다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "direct_product_trial",
            "worldbuilding_exploration",
        ],
    },
    {
        "case_id": "T-007",
        "brand": "Oakley",
        "event_name": "Push As You Are - Oakley Meta Pop-up",
        "published_at": "2026-06-15",
        "location": "서울 성수",
        "youtube_url": "https://www.youtube.com/watch?v=qqEX2RVc9wE",
        "verification_url": (
            "https://www.newswire.co.kr/"
            "newsRead.php?no=1036026"
        ),
        "verification_source_type": "press_release",
        "observation": (
            "방문자가 스탬프 투어를 진행하며 Oakley Meta "
            "AI 글래스를 직접 착용하고 주요 기능을 체험한다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "direct_product_trial",
        ],
    },
    {
        "case_id": "T-008",
        "brand": "Riot Games",
        "event_name": "TFT Wild Fanfest",
        "published_at": "2026-08-21",
        "location": "더현대 서울",
        "youtube_url": "https://www.youtube.com/watch?v=MVlGbr52ac0",
        "verification_url": (
            "https://teamfighttactics.leagueoflegends.com/"
            "ko-kr/news/notices/"
            "tft-wild-fanfest-hyundai-seoul-guide/"
        ),
        "verification_source_type": "official_web",
        "observation": (
            "방문자가 TFT의 신비의 숲 세계관을 구현한 공간에서 "
            "7개 미션을 수행하고 스탬프를 모아 "
            "리워드 프로그램에 참여한다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "worldbuilding_exploration",
        ],
    },

    {
        "case_id": "T-009",
        "brand": "Samsung Electronics",
        "event_name": "2026 Mexico K-Expo AI Experience",
        "published_at": "2026-09-27",
        "location": "Mexico City World Trade Center",
        "youtube_url": None,
        "verification_url": (
            "https://news.samsung.com/kr/"
            "%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90-2026-%EB%A9%95%EC%8B%9C%EC%BD%94-k-"
            "%EB%B0%95%EB%9E%8C%ED%9A%8C%EC%84%9C-ai-%EC%97%B0%EA%B2%B0-%EA%B2%BD%ED%97%98-"
            "%EC%84%A0%EB%B3%B4%EC%97%AC"
        ),
        "verification_source_type": "official_web",
        "verification_published_at": "2026-09-27",
        "observation": (
            "방문자가 Galaxy Z 시리즈와 Galaxy AI를 직접 사용해 "
            "사진·영상 촬영과 콘텐츠 제작을 체험한다."
        ),
        "taxonomy_tags": [
            "direct_product_trial",
        ],
    },
    {
        "case_id": "T-010",
        "brand": "서울관광재단",
        "event_name": "Light Up Your SEOUL - 서울의 밤, 반짝임을 켜다",
        "published_at": "2026-09-23",
        "location": "스타필드 코엑스몰 라이브플라자",
        "youtube_url": None,
        "verification_url": "https://sto.or.kr/press/16684_/16684",
        "verification_source_type": "official_web",
        "verification_published_at": "2026-09-23",
        "observation": (
            "방문자가 서울의 밤을 테마로 구성된 공간을 둘러보고 "
            "야간관광 설문과 별도 현장 미션에 참여해 엽서·포스터 등의 리워드를 받는다."
        ),
        "taxonomy_tags": [
            "mission_journey",
            "worldbuilding_exploration",
        ],
    },
]


# =========================================================
# 4. 시간 관련 함수
# =========================================================

def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def get_reference_date(request: SpotRequest) -> date:
    research = request.get("research", {})

    reference_date = research.get("reference_date")

    if reference_date:
        return date.fromisoformat(reference_date)

    requested_at = request.get("requested_at")

    if requested_at:
        return date.fromisoformat(requested_at[:10])

    return datetime.now(KST).date()


def get_lookback_days(request: SpotRequest) -> int:
    research = request.get("research", {})

    value = research.get("lookback_days", 180)

    try:
        days = int(value)
    except (TypeError, ValueError):
        return 180

    if days <= 0:
        return 180

    return days


# =========================================================
# 5. 날짜 기준 사례 필터
# =========================================================

def filter_cases_by_period(
    cases: list[dict[str, Any]],
    reference_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:

    start_date = reference_date - timedelta(days=lookback_days)

    filtered = []

    for case in cases:
        published_at = date.fromisoformat(case["published_at"])

        if start_date <= published_at <= reference_date:
            filtered.append(case)

    return filtered


# =========================================================
# 6. Sources 생성
# =========================================================

def build_sources(
    cases: list[dict[str, Any]],
    collected_at: str,
) -> list[dict[str, Any]]:

    sources = []

    for case in cases:
        case_number = case["case_id"].split("-")[-1]

        if case.get("youtube_url"):
            sources.append(
                {
                    "source_id": f"S-T-{case_number}-YT",
                    "source_name": (
                        f"{case['brand']} - "
                        f"{case['event_name']} YouTube"
                    ),
                    "source_type": "youtube",
                    "source_url": case["youtube_url"],
                    "published_at": case["published_at"],
                    "collected_at": collected_at,
                }
            )

        sources.append(
            {
                "source_id": f"S-T-{case_number}-WEB",
                "source_name": (
                    f"{case['brand']} - "
                    f"{case['event_name']} verification"
                ),
                "source_type": case["verification_source_type"],
                "source_url": case["verification_url"],
                "published_at": case.get("verification_published_at"),
                "collected_at": collected_at,
            }
        )

    return sources



# =========================================================
# 7. Insights 생성
# =========================================================

def build_insights(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    insights = []

    for case in cases:
        case_number = case["case_id"].split("-")[-1]

        source_ids = []

        if case.get("youtube_url"):
            source_ids.append(f"S-T-{case_number}-YT")

        source_ids.append(f"S-T-{case_number}-WEB")

        insights.append(
            {
                "insight_id": f"I-T-{case_number}",
                "type": "experiential_marketing_case",
                "case_id": case["case_id"],
                "brand": case["brand"],
                "case_name": case["event_name"],
                "location": case["location"],
                "observation": case["observation"],
                "taxonomy_tags": case["taxonomy_tags"],
                "source_ids": source_ids,
            }
        )

    return insights



# =========================================================
# 8. 반복 패턴 생성
# =========================================================

def build_patterns(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    pattern_case_ids: dict[str, list[str]] = {}

    for case in cases:
        for tag in case["taxonomy_tags"]:

            if tag not in PATTERN_DEFINITIONS:
                continue

            pattern_case_ids.setdefault(
                tag,
                [],
            ).append(case["case_id"])

    patterns = []

    for tag, case_ids in pattern_case_ids.items():

        if len(case_ids) < MIN_PATTERN_EVIDENCE:
            continue

        source_ids = [
            f"S-T-{case_id.split('-')[-1]}-WEB"
            for case_id in case_ids
        ]

        definition = PATTERN_DEFINITIONS[tag]

        patterns.append(
            {
                "pattern_id": (
                    f"P-T-{len(patterns) + 1:03d}"
                ),
                "taxonomy_tag": tag,
                "name": definition["name"],
                "description": definition["description"],
                "evidence_count": len(case_ids),
                "example_case_ids": case_ids,
                "example_source_ids": source_ids,
            }
        )

    patterns.sort(
        key=lambda item: (
            -item["evidence_count"],
            item["taxonomy_tag"],
        )
    )

    return patterns


# =========================================================
# 9. Summary 생성
# =========================================================

def build_summary(
    cases: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
) -> str:

    if not cases:
        return (
            "요청 기간 내 검증된 체험형 마케팅 사례를 "
            "확보하지 못했습니다."
        )

    if not patterns:
        return (
            f"검증된 체험형 마케팅 사례 {len(cases)}건을 "
            "확보했으나 반복 패턴을 충분히 확인하지 못했습니다."
        )

    pattern_text = ", ".join(
        (
            f"{pattern['name']} "
            f"({pattern['evidence_count']}건)"
        )
        for pattern in patterns[:3]
    )

    return (
        f"검증된 체험형 마케팅 사례 {len(cases)}건에서 "
        f"{pattern_text} 패턴이 반복적으로 확인되었습니다."
    )


# =========================================================
# 10. 실제 Trend Scout
# =========================================================

def run_trend_scout(
    request: SpotRequest,
) -> ScoutResult:

    started_at = now_iso()

    try:
        reference_date = get_reference_date(request)
        lookback_days = get_lookback_days(request)

        start_date = (
            reference_date
            - timedelta(days=lookback_days)
        )

        selected_cases = filter_cases_by_period(
            VERIFIED_CASES,
            reference_date,
            lookback_days,
        )

        collected_at = now_iso()

        sources = build_sources(
            selected_cases,
            collected_at,
        )

        insights = build_insights(
            selected_cases,
        )

        patterns = build_patterns(
            selected_cases,
        )

        warnings: list[str] = [
            "CURATED_VERIFIED_CASE_POOL_USED",
            "NO_LIVE_API_CALL",
            "REQUEST_RELEVANCE_FILTER_NOT_IMPLEMENTED",
        ]

        if len(selected_cases) < MIN_CONFIRMED_CASES:
            warnings.append(
                "INSUFFICIENT_VERIFIED_CASES_WITHIN_LOOKBACK"
            )

        if len(patterns) < 2:
            warnings.append(
                "INSUFFICIENT_REPEATED_PATTERN_EVIDENCE"
            )

        if (
            len(selected_cases) >= MIN_CONFIRMED_CASES
            and len(patterns) >= 2
        ):
            status = "success"

        elif selected_cases:
            status = "partial"

        else:
            status = "failed"

        campaign = request.get("campaign", {})
        store = request.get("store", {})

        result: dict[str, Any] = {
            "schema_version": "0.1",

            "request_id": request.get(
                "request_id",
                "unknown",
            ),

            "module": "trend",

            "status": status,

            "started_at": started_at,

            "finished_at": now_iso(),

            "query_context": {
                "reference_date": (
                    reference_date.isoformat()
                ),

                "lookback_days": lookback_days,

                "period_start": (
                    start_date.isoformat()
                ),

                "period_end": (
                    reference_date.isoformat()
                ),

                "store_name": store.get("name"),

                "store_address": store.get("address"),

                "campaign_purpose": campaign.get(
                    "purpose"
                ),

                "campaign_product": campaign.get(
                    "product"
                ),

                "verified_case_pool_count": len(
                    VERIFIED_CASES
                ),

                "selected_case_count": len(
                    selected_cases
                ),

                "selection_mode": (
                    "curated_verified_cases"
                ),
            },

            "summary": build_summary(
                selected_cases,
                patterns,
            ),

            "insights": insights,

            # Trend 전용 확장 필드
            "patterns": patterns,

            "sources": sources,

            "warnings": warnings,

            "errors": [],
        }

        return cast(
            ScoutResult,
            result,
        )

    except Exception as error:

        result: dict[str, Any] = {
            "schema_version": "0.1",

            "request_id": request.get(
                "request_id",
                "unknown",
            ),

            "module": "trend",

            "status": "failed",

            "started_at": started_at,

            "finished_at": now_iso(),

            "query_context": {},

            "summary": (
                "Trend Scout 실행 중 오류가 발생했습니다."
            ),

            "insights": [],

            "patterns": [],

            "sources": [],

            "warnings": [],

            "errors": [
                str(error)
            ],
        }

        return cast(
            ScoutResult,
            result,
        )