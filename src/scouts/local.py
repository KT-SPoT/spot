"""Evidence-backed Local Scout proof of concept for SPOT v0.1.

Week 1 intentionally uses a curated evidence set for one test area instead of
pretending to support arbitrary locations. The public function keeps the
shared ``SpotRequest -> ScoutResult`` boundary and returns ``partial`` for
locations outside the validated area.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.contracts import ScoutResult, SpotRequest


KST = timezone(timedelta(hours=9))
TEST_AREA = "부산광역시 강서구 에코델타시티·명지 생활권"
COLLECTED_AT = "2026-09-22T14:47:08+09:00"
VERIFIED_AT = "2026-09-30T00:00:00+09:00"
MINIMUM_EVIDENCE_COUNT = 3

SUCCESSFUL_QUERIES = [
    "에코델타시티 자율주행 모빌리티 서비스 개시 2026 3월",
    "에코델타시티 트램 광역교통개선대책 변경 승인 2026 6월",
    "에코델타시티 15BL 특화주택 993호 2026 7월",
    "site:busan.go.kr/nbtnewsBU 에코델타 2026",
]

FAILED_QUERIES = [
    {
        "query": "부산 명지동 2026 변화 개통 학교 입주 시설",
        "reason": "학교 일반정보와 부동산 집계가 주로 노출되어 최근 변화 근거로 사용하지 않음",
    },
    {
        "query": "site:bsgangseo.go.kr 명지동 2026 개관 착공 준공",
        "reason": "게시일과 구체적 변화가 함께 확인되는 적격 결과를 확보하지 못함",
    },
]

SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "S-L-001",
        "source_name": "부산광역시",
        "source_type": "government",
        "source_url": "https://www.busan.go.kr/nbtnewsBU/1724793",
        "title": "에코델타 국가시범도시 자율주행 모빌리티 서비스 개시",
        "published_at": "2026-03-29",
        "collected_at": COLLECTED_AT,
        "verification": {
            "verified_at": VERIFIED_AT,
            "method": "search result snippet",
            "excerpt": "3월 30일 오픈식, 자율주행버스는 4월부터 시범 운행 예정",
            "note": "원 URL 직접 열람은 시간 초과였으나, 부산시 검색 색인에 게시일과 예정 단계가 표시됐다.",
        },
    },
    {
        "source_id": "S-L-003",
        "source_name": "뉴스핌",
        "source_type": "news",
        "source_url": "https://www.newspim.com/news/view/20260624000204",
        "title": "부산시, 에코델타시티 광역교통대책 변경 승인…강서선 트램 도입 확정",
        "published_at": "2026-06-24",
        "collected_at": COLLECTED_AT,
        "verification": {
            "verified_at": VERIFIED_AT,
            "method": "article body",
            "excerpt": "변경안 최종 승인과 BRT 대신 6.6km 강서선 트램 반영",
            "note": "본문의 2026-06-24 기사입력 시각과 핵심 사실을 직접 확인했다.",
        },
    },
    {
        "source_id": "S-L-004",
        "source_name": "한국일보",
        "source_type": "news",
        "source_url": "https://www.hankookilbo.com/news/article/amp/A2026062410270000876",
        "title": "부산 에코델타시티에 트램 도입… 2034년까지 추진 계획",
        "published_at": "2026-06-24",
        "collected_at": COLLECTED_AT,
        "verification": {
            "verified_at": VERIFIED_AT,
            "method": "article body",
            "excerpt": "광역교통개선대책 변경 승인과 BRT 대신 트램 도입 계획",
            "note": "본문의 2026-06-24 입력 시각과 계획 단계 표현을 직접 확인했다.",
        },
    },
    {
        "source_id": "S-L-005",
        "source_name": "부산광역시",
        "source_type": "government",
        "source_url": "https://www.busan.go.kr/nbtnewsBU/1738442",
        "title": "부산시·부산도시공사, 부산시 최초 특화주택 공모사업 선정!",
        "published_at": "2026-07-03",
        "collected_at": COLLECTED_AT,
        "verification": {
            "verified_at": VERIFIED_AT,
            "method": "article body",
            "excerpt": "에코델타시티 15BL 최종 선정, 총 993호 공급, 2029년 6월 준공 목표",
            "note": "부산시 보도자료 본문의 작성일과 부제목을 직접 확인했다.",
        },
    },
    {
        "source_id": "S-L-006",
        "source_name": "뉴스핌",
        "source_type": "news",
        "source_url": "https://www.newspim.com/news/view/20260703000063",
        "title": "부산시 첫 '특화주택 공모사업' 선정…산업단지 근로자 정주 지원",
        "published_at": "2026-07-03",
        "collected_at": COLLECTED_AT,
        "verification": {
            "verified_at": VERIFIED_AT,
            "method": "article body",
            "excerpt": "15BL 사업 최종 선정과 총 993호 규모의 공공임대 공급 계획",
            "note": "본문의 2026-07-03 기사입력 시각과 사업 단계·규모를 직접 확인했다.",
        },
    },
]

INSIGHTS: list[dict[str, Any]] = [
    {
        "insight_id": "L-001",
        "event_key": "edc-autonomous-mobility-scheduled-2026-03",
        "title": "자율주행 모빌리티 오픈식·시범운행 예정 공지",
        "evidence": (
            "2026년 3월 29일 부산시 보도자료는 다음 날 오픈식과 4월부터의 "
            "자율주행버스 시범 운행을 예정된 일정으로 공지했다."
        ),
        "published_at": "2026-03-29",
        "source_ids": ["S-L-001"],
        "locality_tags": ["에코델타시티", "교통", "스마트시티"],
        "change_state": "scheduled_launch",
        "why_it_matters": (
            "기준일 시점에는 실제 운영 개시가 아니라, 주민 이동서비스 도입을 "
            "앞둔 일정이 공개됐다는 근거다."
        ),
    },
    {
        "insight_id": "L-002",
        "event_key": "gangseo-tram-plan-approved-2026-06",
        "title": "광역교통계획의 강서선 트램 전환 승인",
        "evidence": (
            "2026년 6월 24일 보도는 에코델타시티 광역교통개선대책 변경안이 "
            "최종 승인됐고, 기존 BRT 대신 연장 6.6km 강서선 트램을 반영했다고 전했다."
        ),
        "published_at": "2026-06-24",
        "source_ids": ["S-L-003", "S-L-004"],
        "locality_tags": ["에코델타시티", "명지", "교통", "개발계획"],
        "change_state": "approved_plan",
        "why_it_matters": (
            "명지·에코델타 생활권의 접근성과 유동 경로를 바꿀 수 있는 구체적인 "
            "교통계획 변경이다."
        ),
    },
    {
        "insight_id": "L-003",
        "event_key": "edc-15bl-special-housing-selected-2026-07",
        "title": "청년·산단근로자 특화 공공임대주택 993호 선정",
        "evidence": (
            "2026년 상반기 특화주택 공모에 에코델타시티 15BL 사업이 선정됐다. "
            "청년·산단근로자용 200호를 포함해 총 993호와 육아친화시설을 "
            "공급하며 2029년 준공을 목표로 한다."
        ),
        "published_at": "2026-07-03",
        "source_ids": ["S-L-005", "S-L-006"],
        "locality_tags": ["에코델타시티", "주거", "청년", "육아", "개발계획"],
        "change_state": "selected_future_project",
        "why_it_matters": (
            "향후 산업단지 근로자·청년·육아가구 중심의 정주 수요가 확대될 "
            "가능성을 보여주는 구체적인 공급계획이다."
        ),
    },
]


def _now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _request_text(request: SpotRequest) -> str:
    store = request.get("store") or {}
    return " ".join(str(store.get(key) or "") for key in ("name", "address"))


def _is_supported_area(request: SpotRequest) -> bool:
    text = _request_text(request)
    has_gangseo = "강서구" in text
    has_local_anchor = any(anchor in text for anchor in ("명지", "에코델타", "강동동"))
    return has_gangseo and has_local_anchor


def _reference_date(request: SpotRequest) -> date:
    research = request.get("research") or {}
    raw_reference = research.get("reference_date")
    if isinstance(raw_reference, str):
        try:
            return date.fromisoformat(raw_reference)
        except ValueError:
            pass

    requested_at = request.get("requested_at")
    if isinstance(requested_at, str):
        try:
            return datetime.fromisoformat(requested_at).date()
        except ValueError:
            pass

    return datetime.now(KST).date()


def _lookback_days(request: SpotRequest) -> int:
    research = request.get("research") or {}
    value = research.get("lookback_days", 180)
    return value if isinstance(value, int) and value >= 0 else 180


def _build_summary(
    insights: list[dict[str, Any]],
    *,
    reference_date: date,
    lookback_start: date,
) -> str:
    """Describe only the evidence returned for the requested time window."""

    if not insights:
        return (
            f"{TEST_AREA}에서 {lookback_start.isoformat()}~{reference_date.isoformat()} "
            "조회기간 내 확인 가능한 지역 변화 근거가 없다."
        )

    returned_events = ", ".join(
        f"{insight['title']}({insight['change_state']})" for insight in insights
    )
    return (
        f"{TEST_AREA}에서 {lookback_start.isoformat()}~{reference_date.isoformat()} "
        f"조회기간 내 최근 변화 {len(insights)}건을 확인했다: {returned_events}."
    )


def _empty_result(
    request: SpotRequest,
    started_at: str,
    *,
    warning: str,
) -> ScoutResult:
    return {
        "schema_version": "0.1",
        "request_id": request.get("request_id", "unknown"),
        "module": "local",
        "status": "partial",
        "started_at": started_at,
        "finished_at": _now_iso(),
        "query_context": {
            "test_area": TEST_AREA,
            "requested_store": deepcopy(request.get("store") or {}),
            "successful_queries": deepcopy(SUCCESSFUL_QUERIES),
            "failed_queries": deepcopy(FAILED_QUERIES),
        },
        "summary": "검증된 테스트 지역과 일치하지 않아 지역 변화 근거를 반환하지 않았다.",
        "insights": [],
        "sources": [],
        "warnings": [warning],
        "errors": [],
    }


def run_local_scout(request: SpotRequest) -> ScoutResult:
    """Return curated recent-change evidence for the Week-1 test area.

    Sources that describe the same event are referenced by one insight through
    multiple ``source_ids``. This prevents duplicate articles from inflating
    the local-change count.
    """

    started_at = _now_iso()
    if not _is_supported_area(request):
        return _empty_result(
            request,
            started_at,
            warning="UNSUPPORTED_AREA_WEEK1_POC: 에코델타시티·명지 생활권만 검증됨",
        )

    reference_date = _reference_date(request)
    lookback_days = _lookback_days(request)
    lookback_start = reference_date - timedelta(days=lookback_days)

    insights = [
        deepcopy(insight)
        for insight in INSIGHTS
        if lookback_start <= date.fromisoformat(insight["published_at"]) <= reference_date
    ]
    source_ids = {
        source_id
        for insight in insights
        for source_id in insight["source_ids"]
    }
    sources = [
        deepcopy(source) for source in SOURCES if source["source_id"] in source_ids
    ]

    warnings: list[str] = []
    returned_states = {insight["change_state"] for insight in insights}
    if "scheduled_launch" in returned_states:
        warnings.append(
            "자율주행 모빌리티는 기준일 당시 오픈식·시범운행 예정 공지 단계이며, "
            "실제 운영 개시를 뜻하지 않는다."
        )
    if "approved_plan" in returned_states:
        warnings.append("트램은 변경계획 승인 단계이며 개통된 시설이 아니다.")
    if "selected_future_project" in returned_states:
        warnings.append("특화주택은 공모 선정 단계이며 현재 입주가 완료됐다는 의미가 아니다.")
    radius_m = (request.get("research") or {}).get("radius_m")
    if radius_m is not None:
        warnings.append(
            "WEEK1_AREA_SCOPE: 근거는 개별 점포 반경이 아니라 에코델타시티·명지 생활권 단위다."
        )

    status = "success" if len(insights) >= MINIMUM_EVIDENCE_COUNT else "partial"
    if status == "partial":
        warnings.append(
            f"INSUFFICIENT_RECENT_EVIDENCE: 조회기간 내 변화가 {len(insights)}건으로 "
            f"최소 기준 {MINIMUM_EVIDENCE_COUNT}건보다 적다."
        )

    return {
        "schema_version": "0.1",
        "request_id": request.get("request_id", "unknown"),
        "module": "local",
        "status": status,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "query_context": {
            "test_area": TEST_AREA,
            "requested_store": deepcopy(request.get("store") or {}),
            "reference_date": reference_date.isoformat(),
            "lookback_days": lookback_days,
            "lookback_start": lookback_start.isoformat(),
            "successful_queries": deepcopy(SUCCESSFUL_QUERIES),
            "failed_queries": deepcopy(FAILED_QUERIES),
            "duplicate_policy": "동일 사건의 복수 보도는 source_ids로 묶고 insight 1건으로 계산",
        },
        "summary": _build_summary(
            insights,
            reference_date=reference_date,
            lookback_start=lookback_start,
        ),
        "insights": insights,
        "sources": sources,
        "warnings": warnings,
        "errors": [],
    }
