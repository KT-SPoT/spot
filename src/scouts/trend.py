"""Trend Scout — owner: 김건희.

Week-1:
- Use a curated pool of verified experiential-marketing cases.
- Preserve source publication / verification metadata.
- Filter cases using SpotRequest.research reference_date / lookback_days.
- Extract repeated experience patterns and return ScoutResult v0.1.

Week-2:
- Convert SpotRequest context into YouTube search queries.
- Call YouTube Data API search.list when YOUTUBE_API_KEY is available.
- Normalize, de-duplicate and experimentally score live YouTube candidates.
- Select reference cases from the curated verified pool using transparent
  heuristic signals, then explain why each case may be applicable and
  what limitations should be considered.
- Final automatic relevance judgement is explicitly NOT implemented.
"""

from datetime import date, datetime, time, timedelta, timezone
import json
import os
import re
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from src.contracts import ScoutResult, SpotRequest


# =========================================================
# 1. 기본 설정
# =========================================================

KST = timezone(timedelta(hours=9))

MIN_CONFIRMED_CASES = 5
MIN_PATTERN_EVIDENCE = 2
REFERENCE_CASE_LIMIT = 5

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_MAX_RESULTS_PER_QUERY = 20
YOUTUBE_REGION_CODE = "KR"
YOUTUBE_RELEVANCE_LANGUAGE = "ko"

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

VERIFIED_CASES: list[dict[str, Any]] = [{'case_id': 'T-001',
  'brand': 'Hermès',
  'event_name': "Mystery at the Grooms'",
  'published_at': '2026-06-08',
  'location': '서울 DDP',
  'youtube_url': 'https://www.youtube.com/watch?v=4JsAObYs6iM',
  'verification_url': 'https://www.hermes.com/kr/ko/content/401129-mystery-at-the-grooms-kr/',
  'verification_source_type': 'official_web',
  'verification_published_at': None,
  'verification_published_at_note': 'Hermès 공식 행사 페이지에 게시일이 표시되지 않아 확인 불가. 행사 기간(2026-06-06~06-16)만 명시됨.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '공식 페이지는 DDP 행사에서 방문자가 에르메스 탐정이 되어 흩어진 단서를 따라 제한 시간 안에 숨은 말을 찾는 인터랙티브 게임이라고 설명한다.',
  'observation': '방문자가 에르메스의 탐정 역할을 맡아 공간에 흩어진 단서를 따라 제한 시간 내 숨은 말을 찾는다.',
  'taxonomy_tags': ['mission_journey', 'worldbuilding_exploration']},
 {'case_id': 'T-002',
  'brand': '현대자동차',
  'event_name': 'Youth Adventure 2026',
  'published_at': '2026-06-01',
  'location': '현대 모터스튜디오 부산',
  'youtube_url': 'https://www.youtube.com/watch?v=qOcUFhwaKkY',
  'verification_url': 'https://www.hyundai.com/worldwide/en/brand-journal/lifestyle/teenieping-again-chu',
  'verification_source_type': 'official_web',
  'verification_published_at': '2026-04-30',
  'verification_published_at_note': 'Hyundai Worldwide Brand Journal에 April 30, 2026으로 명시됨.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '현대자동차 공식 글은 부산 모터스튜디오까지 전시를 확대했고, 어린이가 수소 에너지와 NEXO를 보고·만지고·탐색하는 인터랙티브 프로그램이라고 설명한다.',
  'observation': '캐치! 티니핑 IP를 활용한 공간에서 방문자가 수소 에너지와 차량 관련 콘텐츠를 체험하고 게임존 형태의 프로그램에 참여한다.',
  'taxonomy_tags': ['direct_product_trial', 'worldbuilding_exploration']},
 {'case_id': 'T-003',
  'brand': 'KT',
  'event_name': 'Galaxy Z Flip8·Fold8 체험공간',
  'published_at': '2026-07-24',
  'location': '전국 KT 주요 매장',
  'youtube_url': 'https://www.youtube.com/watch?v=aJjrC8FII8g',
  'verification_url': 'https://www.sentv.co.kr/article/view/sentv202607240038',
  'verification_source_type': 'news',
  'verification_published_at': None,
  'verification_published_at_note': '2026-09-30 재확인 시 서울경제TV 원문이 502로 응답해 게시일을 독립 검증하지 못함. URL 식별자만으로 날짜를 '
                                    '추정하지 않음.',
  'verification_status': 'needs_recheck',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '현재 자동 재검증에서는 원문 본문을 확보하지 못해 기존 관찰 문구의 원문 재확인이 필요하다. YouTube 원출처와 수집 기록은 유지하되 병합 전 수동 '
                      '재확인을 권장한다.',
  'observation': '방문자가 Galaxy Z Flip8·Fold8의 주요 기능을 직접 사용하며 미션을 수행하고 완료 단계에 따라 기념품을 받는다.',
  'taxonomy_tags': ['mission_journey', 'direct_product_trial']},
 {'case_id': 'T-004',
  'brand': 'Roblox × MUSINSA',
  'event_name': 'MY LIFE WITH ROBLOX 2026',
  'published_at': '2026-07-27',
  'location': '서울 성수',
  'youtube_url': 'https://www.youtube.com/watch?v=ClSmrCm869I',
  'verification_url': 'https://m.musinsa.com/content/1528923777154874918',
  'verification_source_type': 'official_web',
  'verification_published_at': None,
  'verification_published_at_note': '무신사 콘텐츠 페이지에 행사 기간은 표시되지만 콘텐츠 게시일은 노출되지 않아 확인 불가.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '무신사 공식 콘텐츠는 성수의 여러 팝업과 로블록스 공간을 연결하고, 게임 플레이·보물찾기·현장 체험 등 미션을 수행해 스탬프와 리워드를 받는 구조를 '
                      '설명한다.',
  'observation': '방문자가 성수의 무신사 공간과 Roblox 세계를 연결해 탐험하고 미니게임과 보물찾기 콘텐츠에 참여한다.',
  'taxonomy_tags': ['mission_journey', 'worldbuilding_exploration']},
 {'case_id': 'T-005',
  'brand': '신일전자',
  'event_name': '신일 바람 정거장',
  'published_at': '2026-09-08',
  'location': '서울시청 광장',
  'youtube_url': 'https://www.youtube.com/watch?v=PC2DGzZPjiY',
  'verification_url': 'https://www.shinil.co.kr/ko/press/press.html?b_class=2&b_no=131&mode=VIEW_FORM',
  'verification_source_type': 'official_web',
  'verification_published_at': '2026-09-21',
  'verification_published_at_note': '신일전자 페이지 등록일은 2026-09-21 09:48:17. 제목의 [260908]과 본문은 행사 종료 발표 시점을 가리키지만 '
                                    'source 게시일은 등록일을 사용.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '신일전자 공식 보도자료는 방문객이 선풍기·서큘레이터 등 제품을 직접 살펴보고 경험하며, 추억의 뽑기 이벤트와 쿠폰·굿즈 제공 프로그램에 참여했다고 '
                      '설명한다.',
  'observation': '방문자가 신일의 생활가전을 직접 살펴보고 경험하며 추억의 뽑기 이벤트에 참여해 쿠폰과 굿즈를 받는다.',
  'taxonomy_tags': ['direct_product_trial']},
 {'case_id': 'T-006',
  'brand': 'Dyson',
  'event_name': 'Supersonic Travel Lounge',
  'published_at': '2026-04-23',
  'location': '서울 성수',
  'youtube_url': 'https://www.youtube.com/watch?v=XVQrSzl2uls',
  'verification_url': 'https://www.asiae.co.kr/article/enterprise-CEO/2026042316120439640',
  'verification_source_type': 'news',
  'verification_published_at': '2026-04-23',
  'verification_published_at_note': '아시아경제 기사 입력 시각 2026-04-23 16:12 확인.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '기사에는 방문객이 패스포트와 항공권을 받고 여행지를 고른 뒤 공항 콘셉트 공간에서 스탬프 미션을 수행하고 슈퍼소닉 트래블 제품을 체험한다고 적혀 있다.',
  'observation': '방문자가 여권과 항공권을 받고 여행지를 선택한 뒤 공항 콘셉트 공간을 이동하며 스탬프 미션을 수행하고 Supersonic Travel 제품을 직접 체험한다.',
  'taxonomy_tags': ['mission_journey', 'direct_product_trial', 'worldbuilding_exploration']},
 {'case_id': 'T-007',
  'brand': 'Oakley',
  'event_name': 'Push As You Are - Oakley Meta Pop-up',
  'published_at': '2026-06-15',
  'location': '서울 성수',
  'youtube_url': 'https://www.youtube.com/watch?v=qqEX2RVc9wE',
  'verification_url': 'https://www.newswire.co.kr/newsRead.php?no=1036026',
  'verification_source_type': 'press_release',
  'verification_published_at': '2026-06-08',
  'verification_published_at_note': '뉴스와이어 기사에 2026-06-08 09:59로 명시됨.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '보도자료는 성수 팝업에서 스탬프 투어를 통해 오클리 메타 AI 글래스를 직접 착용하고 제품 기능을 경험할 기회를 제공한다고 설명한다.',
  'observation': '방문자가 스탬프 투어를 진행하며 Oakley Meta AI 글래스를 직접 착용하고 주요 기능을 체험한다.',
  'taxonomy_tags': ['mission_journey', 'direct_product_trial']},
 {'case_id': 'T-008',
  'brand': 'Riot Games',
  'event_name': 'TFT Wild Fanfest',
  'published_at': '2026-08-21',
  'location': '더현대 서울',
  'youtube_url': 'https://www.youtube.com/watch?v=MVlGbr52ac0',
  'verification_url': 'https://teamfighttactics.leagueoflegends.com/ko-kr/news/notices/tft-wild-fanfest-hyundai-seoul-guide/',
  'verification_source_type': 'official_web',
  'verification_published_at': '2026-07-28',
  'verification_published_at_note': 'Riot Games 공지 메타데이터에 2026-07-28T01:00:00Z로 명시됨.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '라이엇 공식 공지는 신비의 숲을 현실 공간으로 구현하고, 방문자가 7개 미션을 수행해 스탬프를 모은 뒤 리워드존에서 보상을 받는 체험존을 설명한다.',
  'observation': '방문자가 TFT의 신비의 숲 세계관을 구현한 공간에서 7개 미션을 수행하고 스탬프를 모아 리워드 프로그램에 참여한다.',
  'taxonomy_tags': ['mission_journey', 'worldbuilding_exploration']},
 {'case_id': 'T-009',
  'brand': 'Samsung Electronics',
  'event_name': '2026 Mexico K-Expo AI Experience',
  'published_at': '2026-09-27',
  'location': 'Mexico City World Trade Center',
  'youtube_url': None,
  'verification_url': 'https://news.samsung.com/kr/%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90-2026-%EB%A9%95%EC%8B%9C%EC%BD%94-k-%EB%B0%95%EB%9E%8C%ED%9A%8C%EC%84%9C-ai-%EC%97%B0%EA%B2%B0-%EA%B2%BD%ED%97%98-%EC%84%A0%EB%B3%B4%EC%97%AC',
  'verification_source_type': 'official_web',
  'verification_published_at': '2026-09-27',
  'verification_published_at_note': 'Samsung Newsroom Korea에 2026/09/27로 명시됨.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '삼성전자 뉴스룸은 관람객이 갤럭시 Z 시리즈와 Galaxy AI로 사진·영상 촬영과 콘텐츠 제작을 직접 체험했다고 설명한다.',
  'observation': '방문자가 Galaxy Z 시리즈와 Galaxy AI를 직접 사용해 사진·영상 촬영과 콘텐츠 제작을 체험한다.',
  'taxonomy_tags': ['direct_product_trial']},
 {'case_id': 'T-010',
  'brand': '서울관광재단',
  'event_name': 'Light Up Your SEOUL - 서울의 밤, 반짝임을 켜다',
  'published_at': '2026-09-23',
  'location': '스타필드 코엑스몰 라이브플라자',
  'youtube_url': None,
  'verification_url': 'https://sto.or.kr/press/16684_/16684',
  'verification_source_type': 'official_web',
  'verification_published_at': '2026-09-23',
  'verification_published_at_note': '서울관광재단 보도자료 작성일 2026-09-23 확인.',
  'verification_status': 'verified',
  'verified_at': '2026-09-30T13:43:21+09:00',
  'evidence_summary': '서울관광재단은 서울의 밤을 주제로 4개 테마 공간을 구성하고 야간관광 설문과 별도 현장 미션 참여자에게 엽서·포스터 등 리워드를 제공한다고 설명한다.',
  'observation': '방문자가 서울의 밤을 테마로 구성된 공간을 둘러보고 야간관광 설문과 별도 현장 미션에 참여해 엽서·포스터 등의 리워드를 받는다.',
  'taxonomy_tags': ['mission_journey', 'worldbuilding_exploration']}]


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


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding existing env vars."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def get_youtube_api_key() -> str | None:
    """Read YOUTUBE_API_KEY from process env or repository-root .env."""
    api_key = os.environ.get("YOUTUBE_API_KEY")

    if api_key:
        return api_key.strip() or None

    load_env_file(Path.cwd() / ".env")
    api_key = os.environ.get("YOUTUBE_API_KEY")

    return api_key.strip() if api_key and api_key.strip() else None


def to_youtube_rfc3339(
    target_date: date,
    *,
    end_of_day: bool = False,
) -> str:
    """Convert a KST date boundary to UTC RFC3339 for YouTube API."""
    boundary_time = time.max if end_of_day else time.min
    local_dt = datetime.combine(
        target_date,
        boundary_time,
        tzinfo=KST,
    )
    utc_dt = local_dt.astimezone(timezone.utc)

    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_youtube_api_error(body: str) -> str:
    """Return a compact API error without exposing credentials."""
    try:
        payload = json.loads(body)
        error = payload.get("error", {})
        message = error.get("message")
        code = error.get("code")

        if message:
            return f"YouTube API error {code}: {message}"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return "YouTube API request failed."


def search_youtube(
    query: str,
    api_key: str,
    published_after: str,
    published_before: str,
    max_results: int = YOUTUBE_MAX_RESULTS_PER_QUERY,
) -> list[dict[str, Any]]:
    """Search YouTube videos and normalize search.list results."""
    params = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "maxResults": max(1, min(int(max_results), 50)),
        "order": "relevance",
        "publishedAfter": published_after,
        "publishedBefore": published_before,
        "regionCode": YOUTUBE_REGION_CODE,
        "relevanceLanguage": YOUTUBE_RELEVANCE_LANGUAGE,
        "safeSearch": "moderate",
        "key": api_key,
    }

    request_url = f"{YOUTUBE_SEARCH_URL}?{urlencode(params)}"

    try:
        with urlopen(request_url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        try:
            body = error.read().decode("utf-8", errors="replace")
        finally:
            # HTTPError owns a response stream, including for HTTP 429.
            # Release it even when reading the error body fails.
            error.close()
        raise RuntimeError(parse_youtube_api_error(body)) from error

    except URLError as error:
        raise RuntimeError(
            f"YouTube API network error: {error.reason}"
        ) from error

    except TimeoutError as error:
        raise RuntimeError("YouTube API request timed out.") from error

    candidates: list[dict[str, Any]] = []

    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})

        if not video_id:
            continue

        candidates.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt"),
                "youtube_url": (
                    f"https://www.youtube.com/watch?v={video_id}"
                ),
                "matched_queries": [query],
            }
        )

    return candidates


def search_youtube_candidates(
    queries: list[str],
    api_key: str,
    reference_date: date,
    lookback_days: int,
    max_results_per_query: int = YOUTUBE_MAX_RESULTS_PER_QUERY,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run all generated searches and de-duplicate candidates by videoId."""
    start_date = reference_date - timedelta(days=lookback_days)

    published_after = to_youtube_rfc3339(start_date)
    published_before = to_youtube_rfc3339(
        reference_date,
        end_of_day=True,
    )

    by_video_id: dict[str, dict[str, Any]] = {}
    api_errors: list[str] = []

    for query in queries:
        try:
            results = search_youtube(
                query=query,
                api_key=api_key,
                published_after=published_after,
                published_before=published_before,
                max_results=max_results_per_query,
            )
        except RuntimeError as error:
            api_errors.append(f"{query}: {error}")
            continue

        for candidate in results:
            video_id = candidate["video_id"]

            if video_id not in by_video_id:
                by_video_id[video_id] = candidate
                continue

            matched_queries = by_video_id[video_id]["matched_queries"]
            for matched_query in candidate["matched_queries"]:
                if matched_query not in matched_queries:
                    matched_queries.append(matched_query)

    candidates = list(by_video_id.values())
    candidates.sort(
        key=lambda item: item.get("published_at") or "",
        reverse=True,
    )

    return candidates, api_errors


def normalize_text(value: Any) -> str:
    """Normalize free text for deterministic keyword scoring."""
    return " ".join(str(value or "").lower().split())


def get_brand_hint(request: SpotRequest) -> str:
    """Use the first token of store name as a lightweight brand hint."""
    store = request.get("store", {})
    store_name = str(store.get("name") or "").strip()

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

    for term in terms["exact"]:
        if term in combined or term in compact_combined:
            return "exact", term

    for term in terms["family"]:
        if term in combined or term in compact_combined:
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


def rank_candidates(
    candidates: list[dict[str, Any]],
    request: SpotRequest,
) -> list[dict[str, Any]]:
    """Score and sort live candidates for later selection."""
    ranked = [
        score_candidate_relevance(candidate, request)
        for candidate in candidates
    ]

    ranked.sort(
        key=lambda item: (
            -int(item.get("is_experiential_candidate", False)),
            -int(item.get("relevance_score", 0)),
            item.get("published_at") or "",
        ),
        reverse=False,
    )

    return ranked


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
) -> list[dict[str, Any]]:

    sources = []

    for case in cases:
        case_number = case["case_id"].split("-")[-1]
        verified_at = case["verified_at"]

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
                    "collected_at": verified_at,
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
                "published_at_note": case.get(
                    "verification_published_at_note"
                ),
                "collected_at": verified_at,
                "verification_status": case.get(
                    "verification_status",
                    "verified",
                ),
                "evidence_summary": case.get("evidence_summary"),
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
# 8. 요청 목적 기준 참고 사례 선택 / 설명
# =========================================================

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


def build_reference_explanation(
    case: dict[str, Any],
    request: SpotRequest,
    signals: list[str],
) -> dict[str, Any]:
    """Explain applicability and limitations in user-facing Korean text."""
    campaign = request.get("campaign", {})
    store = request.get("store", {})

    purpose = str(campaign.get("purpose") or "현재 행사 목적").strip()
    product = str(campaign.get("product") or "").strip()
    region = extract_region(store.get("address"))

    tags = set(case.get("taxonomy_tags") or [])

    reasons: list[str] = []

    if "PRODUCT_OR_FAMILY_MATCH" in signals:
        reasons.append(
            "요청 제품 또는 동일 제품군을 직접 다루는 사례라 제품 체험 방식과 운영 구성을 참고할 수 있습니다."
        )

    if "SAME_BRAND" in signals:
        reasons.append(
            "요청 매장과 같은 브랜드 맥락의 사례라 메시지와 고객 접점 설계를 비교하기 좋습니다."
        )

    if "SAME_REGION" in signals:
        reasons.append(
            "같은 광역 지역에서 진행된 사례라 지역 고객 동선과 행사 운영 맥락을 참고하기 좋습니다."
        )

    if "direct_product_trial" in tags:
        reasons.append(
            "방문자가 제품이나 핵심 기능을 직접 사용하도록 설계되어 신제품 체험 행사 목적과 연결됩니다."
        )

    if "mission_journey" in tags:
        reasons.append(
            "미션·스탬프·리워드 구조를 활용해 단순 전시보다 체류와 참여를 유도한 사례입니다."
        )

    if "worldbuilding_exploration" in tags:
        reasons.append(
            "공간 자체를 탐색 경험으로 만든 사례라 매장 내 체험 동선과 테마 연출을 구상할 때 참고할 수 있습니다."
        )

    if not reasons:
        reasons.append(
            f"{purpose}와 직접 동일한 사례라고 단정할 수는 없지만, 검증된 체험형 마케팅 운영 사례로 비교 참고할 수 있습니다."
        )

    limitations: list[str] = []

    if "SAME_BRAND" not in signals:
        limitations.append(
            "브랜드와 상품 맥락이 다르므로 메시지·혜택·고객 기대를 그대로 적용하기는 어렵습니다."
        )

    case_location = str(case.get("location") or "")
    nationwide_case = "전국" in case_location

    if (
        region
        and "SAME_REGION" not in signals
        and not nationwide_case
    ):
        limitations.append(
            f"요청 지역({region})과 다른 지역 사례이므로 상권·유동인구·공간 조건 차이를 별도로 검토해야 합니다."
        )

    if "worldbuilding_exploration" in tags:
        limitations.append(
            "대형 테마 공간이나 제작물이 필요한 구조는 일반 매장 규모에서는 축소 설계가 필요합니다."
        )

    if "mission_journey" in tags:
        limitations.append(
            "미션·리워드 운영에는 고객 동선 관리, 현장 인력, 경품 재고 같은 추가 운영비가 발생할 수 있습니다."
        )

    if "direct_product_trial" in tags and product:
        limitations.append(
            "실제 제품 체험을 적용하려면 체험 단말, 보안·파손 대응, 직원 안내 역량을 함께 고려해야 합니다."
        )

    if case.get("verification_status") != "verified":
        limitations.insert(
            0,
            "현재 검증 상태가 완전하지 않아 실제 적용 전 원문과 행사 세부 운영 내용을 다시 확인해야 합니다."
        )

    # 너무 길어지지 않도록 핵심 3개까지만 노출
    return {
        "why_relevant": " ".join(reasons[:3]),
        "limitations": " ".join(limitations[:3]),
        "fit_signals": signals,
        "automatic_final_judgement": False,
    }


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


def build_reference_case_outputs(
    cases: list[dict[str, Any]],
    request: SpotRequest,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []

    for case in cases:
        case_number = case["case_id"].split("-")[-1]

        source_ids: list[str] = []
        if case.get("youtube_url"):
            source_ids.append(f"S-T-{case_number}-YT")
        source_ids.append(f"S-T-{case_number}-WEB")

        explanation = build_reference_explanation(
            case,
            request,
            list(case.get("_fit_signals") or []),
        )

        outputs.append(
            {
                "case_id": case["case_id"],
                "brand": case["brand"],
                "case_name": case["event_name"],
                "location": case["location"],
                "observation": case["observation"],
                "taxonomy_tags": case["taxonomy_tags"],
                "reference_priority_score": case.get(
                    "_reference_score",
                    0,
                ),
                "relevance": explanation,
                "source_ids": source_ids,
            }
        )

    return outputs


# =========================================================
# 9. 반복 패턴 생성
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
# 10. Summary 생성
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
# 11. 실제 Trend Scout
# =========================================================

def run_trend_scout(
    request: SpotRequest,
) -> ScoutResult:

    started_at = now_iso()

    try:
        reference_date = get_reference_date(request)
        lookback_days = get_lookback_days(request)
        search_queries = build_search_queries(request)

        start_date = (
            reference_date
            - timedelta(days=lookback_days)
        )

        # 실시간 YouTube 후보 수집 + 실험적 후보 점수화.
        # 이 점수는 최종 자동 관련성 판단이 아니라 후보 정렬용 신호다.
        youtube_api_key = get_youtube_api_key()
        live_candidates: list[dict[str, Any]] = []
        live_api_errors: list[str] = []

        if youtube_api_key:
            live_candidates, live_api_errors = search_youtube_candidates(
                queries=search_queries,
                api_key=youtube_api_key,
                reference_date=reference_date,
                lookback_days=lookback_days,
            )

        ranked_candidates = rank_candidates(
            live_candidates,
            request,
        )

        experiential_candidates = [
            candidate
            for candidate in ranked_candidates
            if candidate.get("is_experiential_candidate")
        ]

        # 기간 내 검증 사례를 만든 뒤,
        # 요청 목적과 비교하기 좋은 참고 사례만 소수로 추린다.
        period_cases = filter_cases_by_period(
            VERIFIED_CASES,
            reference_date,
            lookback_days,
        )

        reference_case_records = select_reference_cases(
            period_cases,
            request,
            limit=REFERENCE_CASE_LIMIT,
        )

        # Week 1 호환 필드:
        # insights / patterns / sources는 기간 내 전체 사례 기준을 유지한다.
        # Week 2 요청 관련 결과는 reference_* 필드로 별도 제공한다.
        sources = build_sources(
            period_cases,
        )

        insights = build_insights(
            period_cases,
        )

        period_patterns = build_patterns(
            period_cases,
        )

        reference_patterns = build_patterns(
            reference_case_records,
        )

        reference_cases = build_reference_case_outputs(
            reference_case_records,
            request,
        )

        warnings: list[str] = [
            "CURATED_VERIFIED_CASE_POOL_USED",
            "AUTOMATIC_FINAL_RELEVANCE_JUDGEMENT_NOT_IMPLEMENTED",
            "REFERENCE_CASE_SELECTION_USES_TRANSPARENT_HEURISTIC",
        ]

        if not youtube_api_key:
            warnings.append(
                "YOUTUBE_API_KEY_MISSING"
            )
        elif live_candidates:
            warnings.append(
                "LIVE_YOUTUBE_SEARCH_USED"
            )
        else:
            warnings.append(
                "LIVE_YOUTUBE_SEARCH_RETURNED_NO_CANDIDATES"
            )

        if live_api_errors:
            warnings.append(
                "LIVE_YOUTUBE_SEARCH_PARTIAL_FAILURE"
            )

        if len(period_cases) < MIN_CONFIRMED_CASES:
            warnings.append(
                "INSUFFICIENT_VERIFIED_CASES_WITHIN_LOOKBACK"
            )

        if len(reference_case_records) < MIN_CONFIRMED_CASES:
            warnings.append(
                "INSUFFICIENT_REFERENCE_CASES_WITHIN_LOOKBACK"
            )

        if len(period_patterns) < 2:
            warnings.append(
                "INSUFFICIENT_REPEATED_PATTERN_EVIDENCE"
            )

        if (
            len(period_cases) >= MIN_CONFIRMED_CASES
            and len(period_patterns) >= 2
        ):
            status = "success"
        elif period_cases:
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
                "reference_date": reference_date.isoformat(),
                "lookback_days": lookback_days,
                "period_start": start_date.isoformat(),
                "period_end": reference_date.isoformat(),
                "store_name": store.get("name"),
                "store_address": store.get("address"),
                "campaign_purpose": campaign.get("purpose"),
                "campaign_product": campaign.get("product"),
                "search_queries": search_queries,
                "live_youtube_candidate_count": len(
                    live_candidates
                ),
                "live_ranked_candidate_count": len(
                    ranked_candidates
                ),
                "live_experiential_candidate_count": len(
                    experiential_candidates
                ),
                "live_youtube_api_error_count": len(
                    live_api_errors
                ),
                "verified_case_pool_count": len(
                    VERIFIED_CASES
                ),
                # Week 1 하위 호환용 필드.
                # 기존 selected_case_count의 의미는 기간 내 선택 사례 수다.
                "selected_case_count": len(
                    period_cases
                ),
                "period_case_count": len(
                    period_cases
                ),
                "reference_case_count": len(
                    reference_case_records
                ),
                "selection_mode": (
                    "curated_verified_reference_cases_"
                    "with_experimental_live_discovery"
                ),
            },

            # Week 1 호환 summary / insights / patterns는 전체 기간 사례 기준.
            "summary": build_summary(
                period_cases,
                period_patterns,
            ),

            "insights": insights,

            "patterns": period_patterns,

            # Week 2 추가 필드:
            # 현재 요청에 맞춘 참고 사례 / 관련 패턴 / 적용 이유와 한계.
            "reference_summary": build_summary(
                reference_case_records,
                reference_patterns,
            ),
            "reference_cases": reference_cases,
            "reference_patterns": reference_patterns,

            "relevance_status": {
                "automatic_final_judgement": "not_implemented",
                "reference_case_selection": (
                    "transparent_heuristic_over_verified_cases"
                ),
                "live_candidate_scoring": (
                    "experimental_rule_based"
                ),
                "note": (
                    "현재 점수와 fit signal은 참고 후보 정렬용이며 "
                    "최종 관련성 판단을 자동화한 것으로 간주하지 않습니다."
                ),
            },

            "sources": sources,

            # 개발/관찰용 실시간 검색 결과
            "live_candidates": ranked_candidates,
            "live_experiential_candidates": experiential_candidates,
            "live_api_errors": live_api_errors,

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
            "reference_summary": "",
            "reference_cases": [],
            "reference_patterns": [],
            "relevance_status": {
                "automatic_final_judgement": "not_implemented",
            },
            "sources": [],
            "live_candidates": [],
            "live_experiential_candidates": [],
            "live_api_errors": [],
            "warnings": [],
            "errors": [
                str(error)
            ],
        }

        return cast(
            ScoutResult,
            result,
        )
