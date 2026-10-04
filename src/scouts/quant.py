"""Quant Scout — SBIZ365 상세분석 기반 정량 리서치.

연결 범위:
- SpotRequest의 위도/경도/반경을 사용한다.
- SBIZ365 상세분석 2/3/4/6/7/8 리포트를 한 번에 수집한다.
- 각 리포트를 전용 파서로 정규화한다.
- 핵심 지표와 인사이트를 ScoutResult v0.1로 반환한다.
- 고객특성/배달매출처럼 원문 데이터가 없는 영역은 값을 추정하지 않고 warning으로 남긴다.
"""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, cast

from dotenv import load_dotenv

from src.contracts import ScoutResult, SpotRequest
from src.scouts.quant_area import parse_area_report
from src.scouts.quant_customer import parse_customer_report
from src.scouts.quant_delivery import parse_delivery_report
from src.scouts.quant_industry import parse_industry_report
from src.scouts.quant_geocode import KakaoGeocodeError, resolve_address
from src.scouts.quant_population import parse_population_report
from src.scouts.quant_sales import parse_sales_report
from src.scouts.quant_sbiz365 import Sbiz365Error, collect_sbiz365_reports


DEFAULT_RADIUS_M = 1000
REPORT_NUMBERS = (2, 3, 4, 6, 7, 8)
CORE_SECTIONS = {"industry", "sales", "population", "area"}

GENDER_LABELS = {
    "male": "남성",
    "female": "여성",
}

AGE_LABELS = {
    "teens": "10대",
    "20s": "20대",
    "30s": "30대",
    "40s": "40대",
    "50s": "50대",
    "60_plus": "60대 이상",
}

DAY_LABELS = {
    "mon": "월요일",
    "tue": "화요일",
    "wed": "수요일",
    "thu": "목요일",
    "fri": "금요일",
    "sat": "토요일",
    "sun": "일요일",
}

TIME_LABELS = {
    "05_09": "05~09시",
    "09_12": "09~12시",
    "12_14": "12~14시",
    "14_18": "14~18시",
    "18_23": "18~23시",
    "23_05": "23~05시",
}

REPORT_PARSERS: dict[int, tuple[str, Callable[[str], dict[str, Any]]]] = {
    2: ("industry", parse_industry_report),
    3: ("sales", parse_sales_report),
    4: ("population", parse_population_report),
    6: ("area", parse_area_report),
    7: ("customer", parse_customer_report),
    8: ("delivery", parse_delivery_report),
}

REPORT_TITLES = {
    2: "업종분석",
    3: "매출분석",
    4: "인구분석",
    6: "지역현황",
    7: "고객특성",
    8: "배달매출",
}


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def _label(mapping: dict[str, str], key: Any) -> str:
    if key is None:
        return "확인 불가"
    return mapping.get(str(key), str(key))


def _value_text(value: Any, suffix: str = "") -> str:
    if value is None:
        return "확인 불가"
    return f"{value}{suffix}"


def _percent_text(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "확인 불가"
    sign = "+" if value > 0 else ""
    return f"{sign}{value}%"


def _failed_result(
    request: SpotRequest,
    started_at: str,
    *,
    code: str,
    message: str,
    query_context: dict[str, Any],
) -> ScoutResult:
    return {
        "schema_version": "0.1",
        "request_id": request.get("request_id", "unknown"),
        "module": "quant",
        "status": "failed",
        "started_at": started_at,
        "finished_at": _now_iso(),
        "query_context": query_context,
        "summary": "Quant Scout 실행에 실패했습니다.",
        "insights": [],
        "sources": [],
        "warnings": [],
        "errors": [
            {
                "code": code,
                "message": message,
            }
        ],
    }


def _parse_reports(
    collected: dict[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    parsed: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    reports = collected.get("reports", {})

    for report_no, (section, parser) in REPORT_PARSERS.items():
        report = reports.get(report_no)
        html = report.get("html") if isinstance(report, dict) else None

        if not html:
            errors.append(
                {
                    "code": f"SBIZ365_REPORT_{report_no}_MISSING",
                    "message": (
                        f"sang_gwon{report_no}.sg ({REPORT_TITLES[report_no]}) "
                        "응답을 찾지 못했습니다."
                    ),
                    "section": section,
                    "report": f"sang_gwon{report_no}.sg",
                }
            )
            continue

        try:
            normalized = parser(html)
        except Exception as exc:
            errors.append(
                {
                    "code": f"SBIZ365_REPORT_{report_no}_PARSE_ERROR",
                    "message": str(exc),
                    "section": section,
                    "report": f"sang_gwon{report_no}.sg",
                }
            )
            continue

        parsed[section] = normalized

        for warning in normalized.get("warnings", []):
            if isinstance(warning, dict):
                warnings.append(
                    {
                        **warning,
                        "section": section,
                        "report": f"sang_gwon{report_no}.sg",
                    }
                )
            else:
                warnings.append(
                    {
                        "code": "SBIZ365_PARSER_WARNING",
                        "message": str(warning),
                        "section": section,
                        "report": f"sang_gwon{report_no}.sg",
                    }
                )

    return parsed, warnings, errors


def _build_insights(
    metrics: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []

    industry = metrics.get("industry", {}).get("derived_selected_area", {})
    latest_store_count = industry.get("latest_store_count")
    store_yoy = industry.get("year_over_year_change_percent_reported")
    if store_yoy is None:
        store_yoy = industry.get("year_over_year_change_percent_computed")
    if latest_store_count is not None:
        insights.append(
            {
                "insight_id": "Q-IND-001",
                "type": "industry",
                "statement": (
                    f"선택 영역의 최신 업소수는 {latest_store_count}개이며, "
                    f"전년동월대비 증감률은 {_percent_text(store_yoy)}입니다."
                ),
                "metric_refs": [
                    "metrics.industry.derived_selected_area.latest_store_count",
                    "metrics.industry.derived_selected_area.year_over_year_change_percent_reported",
                ],
            }
        )

    sales = metrics.get("sales", {}).get("derived_selected_area", {})
    latest_sales = sales.get("latest_monthly_average_sales_amount_10k_krw")
    sales_yoy = sales.get("sales_amount_year_over_year_change_percent_reported")
    if sales_yoy is None:
        sales_yoy = sales.get("sales_amount_year_over_year_change_percent_computed")
    latest_transactions = sales.get("latest_monthly_average_sales_transactions")
    if latest_sales is not None or latest_transactions is not None:
        insights.append(
            {
                "insight_id": "Q-SALES-001",
                "type": "sales",
                "statement": (
                    "선택 영역의 업소당 최신 월평균 매출액은 "
                    f"{_value_text(latest_sales, '만원')}이고 "
                    f"전년동월대비 {_percent_text(sales_yoy)}이며, "
                    "월평균 매출건수는 "
                    f"{_value_text(latest_transactions, '건')}입니다."
                ),
                "metric_refs": [
                    "metrics.sales.derived_selected_area.latest_monthly_average_sales_amount_10k_krw",
                    "metrics.sales.derived_selected_area.sales_amount_year_over_year_change_percent_reported",
                    "metrics.sales.derived_selected_area.latest_monthly_average_sales_transactions",
                ],
            }
        )

    peak_sales_day = sales.get("peak_sales_day")
    peak_sales_time = sales.get("peak_sales_time_band")
    dominant_sales_gender = sales.get("dominant_sales_gender")
    dominant_sales_age = sales.get("dominant_sales_age")
    if any(
        value is not None
        for value in (
            peak_sales_day,
            peak_sales_time,
            dominant_sales_gender,
            dominant_sales_age,
        )
    ):
        insights.append(
            {
                "insight_id": "Q-SALES-002",
                "type": "sales_profile",
                "statement": (
                    "매출 비중이 가장 높은 요일/시간대는 "
                    f"{_label(DAY_LABELS, peak_sales_day)} / "
                    f"{_label(TIME_LABELS, peak_sales_time)}이며, "
                    "매출 기준 주요 성별·연령대는 "
                    f"{_label(GENDER_LABELS, dominant_sales_gender)} / "
                    f"{_label(AGE_LABELS, dominant_sales_age)}입니다."
                ),
                "metric_refs": [
                    "metrics.sales.derived_selected_area.peak_sales_day",
                    "metrics.sales.derived_selected_area.peak_sales_time_band",
                    "metrics.sales.derived_selected_area.dominant_sales_gender",
                    "metrics.sales.derived_selected_area.dominant_sales_age",
                ],
            }
        )

    population = metrics.get("population", {}).get("derived_selected_area", {})
    flow_population = population.get("latest_monthly_daily_flow_population")
    dominant_flow_gender = population.get("dominant_flow_gender")
    dominant_flow_age = population.get("dominant_flow_age")
    if flow_population is not None:
        insights.append(
            {
                "insight_id": "Q-POP-001",
                "type": "population",
                "statement": (
                    f"최신 월 기준 일평균 유동인구는 {flow_population}명이며, "
                    "유동인구에서 비중이 가장 높은 성별·연령대는 "
                    f"{_label(GENDER_LABELS, dominant_flow_gender)} / "
                    f"{_label(AGE_LABELS, dominant_flow_age)}입니다."
                ),
                "metric_refs": [
                    "metrics.population.derived_selected_area.latest_monthly_daily_flow_population",
                    "metrics.population.derived_selected_area.dominant_flow_gender",
                    "metrics.population.derived_selected_area.dominant_flow_age",
                ],
            }
        )

    peak_day = population.get("peak_day_of_week")
    peak_time = population.get("peak_time_band")
    if peak_day is not None or peak_time is not None:
        insights.append(
            {
                "insight_id": "Q-POP-002",
                "type": "population_timing",
                "statement": (
                    "유동인구는 "
                    f"{_label(DAY_LABELS, peak_day)}, "
                    f"{_label(TIME_LABELS, peak_time)}에 가장 집중됩니다."
                ),
                "metric_refs": [
                    "metrics.population.derived_selected_area.peak_day_of_week",
                    "metrics.population.derived_selected_area.peak_time_band",
                ],
            }
        )

    resident = population.get("latest_resident_population_from_trend")
    worker = population.get("latest_worker_population_from_trend")
    if resident is not None or worker is not None:
        insights.append(
            {
                "insight_id": "Q-POP-003",
                "type": "population",
                "statement": (
                    f"최신 주거인구는 {_value_text(resident, '명')}, "
                    f"직장인구는 {_value_text(worker, '명')}입니다."
                ),
                "metric_refs": [
                    "metrics.population.derived_selected_area.latest_resident_population_from_trend",
                    "metrics.population.derived_selected_area.latest_worker_population_from_trend",
                ],
            }
        )

    area = metrics.get("area", {}).get("derived_selected_area", {})
    households = area.get("latest_households")
    dominant_facility = area.get("dominant_facility_type")
    bus_stops = area.get("bus_stop_count")
    subway_stations = area.get("subway_station_count")
    if any(
        value is not None
        for value in (households, dominant_facility, bus_stops, subway_stations)
    ):
        insights.append(
            {
                "insight_id": "Q-AREA-001",
                "type": "area",
                "statement": (
                    f"선택 영역의 최신 세대수는 {_value_text(households, '세대')}이며, "
                    f"가장 많은 주요시설 유형은 {_value_text(dominant_facility)}입니다. "
                    f"인근 지하철역은 {_value_text(subway_stations, '개')}, "
                    f"버스정류장은 {_value_text(bus_stops, '개')}입니다."
                ),
                "metric_refs": [
                    "metrics.area.derived_selected_area.latest_households",
                    "metrics.area.derived_selected_area.dominant_facility_type",
                    "metrics.area.derived_selected_area.subway_station_count",
                    "metrics.area.derived_selected_area.bus_stop_count",
                ],
            }
        )

    customer = metrics.get("customer", {}).get("derived_selected_area", {})
    if customer.get("has_customer_data") is True:
        insights.append(
            {
                "insight_id": "Q-CUST-001",
                "type": "customer",
                "statement": "고객특성 데이터가 제공되어 정규화 결과에 포함했습니다.",
                "metric_refs": [
                    "metrics.customer.derived_selected_area.available_sections"
                ],
            }
        )

    delivery = metrics.get("delivery", {}).get("derived_selected_area", {})
    if delivery.get("has_delivery_sales_data") is True:
        insights.append(
            {
                "insight_id": "Q-DELIVERY-001",
                "type": "delivery",
                "statement": "배달매출 데이터가 제공되어 정규화 결과에 포함했습니다.",
                "metric_refs": [
                    "metrics.delivery.derived_selected_area.has_delivery_sales_data"
                ],
            }
        )

    return insights


def _build_summary(
    admi_nm: str | None,
    metrics: dict[str, dict[str, Any]],
) -> str:
    area_name = admi_nm or "선택 영역"

    industry = metrics.get("industry", {}).get("derived_selected_area", {})
    sales = metrics.get("sales", {}).get("derived_selected_area", {})
    population = metrics.get("population", {}).get("derived_selected_area", {})
    area = metrics.get("area", {}).get("derived_selected_area", {})

    parts: list[str] = []

    store_count = industry.get("latest_store_count")
    if store_count is not None:
        parts.append(f"업소수는 {store_count}개입니다")

    latest_sales = sales.get("latest_monthly_average_sales_amount_10k_krw")
    if latest_sales is not None:
        parts.append(f"업소당 월평균 매출액은 {latest_sales}만원입니다")

    flow_population = population.get("latest_monthly_daily_flow_population")
    if flow_population is not None:
        parts.append(f"일평균 유동인구는 {flow_population}명입니다")

    households = area.get("latest_households")
    if households is not None:
        parts.append(f"세대수는 {households}세대입니다")

    if not parts:
        return f"{area_name}의 SBIZ365 상세분석 리포트를 수집했으나 핵심 지표를 추출하지 못했습니다."

    return f"{area_name} 기준 " + " ".join(parts)


def _build_compact_metrics(
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    industry = metrics.get("industry", {}).get("derived_selected_area", {})
    sales = metrics.get("sales", {}).get("derived_selected_area", {})
    population = metrics.get("population", {}).get("derived_selected_area", {})
    area = metrics.get("area", {}).get("derived_selected_area", {})
    customer = metrics.get("customer", {}).get("derived_selected_area", {})
    delivery = metrics.get("delivery", {}).get("derived_selected_area", {})

    store_yoy = industry.get("year_over_year_change_percent_reported")
    if store_yoy is None:
        store_yoy = industry.get("year_over_year_change_percent_computed")

    sales_yoy = sales.get("sales_amount_year_over_year_change_percent_reported")
    if sales_yoy is None:
        sales_yoy = sales.get("sales_amount_year_over_year_change_percent_computed")

    compact: dict[str, Any] = {
        # 현재 SBIZ365 상세분석은 선택 업종(G20802) 기준이므로
        # 전체 업종 점포수/카테고리 분포는 이 수집 범위에서 제공되지 않는다.
        "total_store_count": None,
        "telecom_store_count": industry.get("latest_store_count"),
        "category_counts": [],
        "telecom_store_yoy_percent": store_yoy,
        "monthly_avg_sales_10k_krw": sales.get(
            "latest_monthly_average_sales_amount_10k_krw"
        ),
        "monthly_avg_sales_transactions": sales.get(
            "latest_monthly_average_sales_transactions"
        ),
        "sales_yoy_percent": sales_yoy,
        "peak_sales_day": sales.get("peak_sales_day"),
        "peak_sales_time_band": sales.get("peak_sales_time_band"),
        "dominant_sales_gender": sales.get("dominant_sales_gender"),
        "dominant_sales_age": sales.get("dominant_sales_age"),
        "daily_avg_floating_population": population.get(
            "latest_monthly_daily_flow_population"
        ),
        "dominant_floating_gender": population.get("dominant_flow_gender"),
        "dominant_floating_age": population.get("dominant_flow_age"),
        "peak_floating_day": population.get("peak_day_of_week"),
        "peak_floating_time_band": population.get("peak_time_band"),
        "resident_population": population.get(
            "latest_resident_population_from_trend"
        ),
        "worker_population": population.get(
            "latest_worker_population_from_trend"
        ),
        "household_count": area.get("latest_households"),
        "dominant_facility_type": area.get("dominant_facility_type"),
        "school_count": area.get("school_count_total"),
        "student_count": area.get("student_count_total"),
        "subway_station_count": area.get("subway_station_count"),
        "bus_stop_count": area.get("bus_stop_count"),
        "delivery_sales_available": delivery.get("has_delivery_sales_data"),
    }

    if customer.get("has_customer_data") is True:
        compact["customer"] = {
            "dominant_visitor_gender": customer.get("dominant_visitor_gender"),
            "dominant_customer_type": customer.get("dominant_customer_type"),
            "top_male_lifestyle": (
                customer.get("top_male_lifestyle_excluding_other") or {}
            ).get("name"),
            "top_female_lifestyle": (
                customer.get("top_female_lifestyle_excluding_other") or {}
            ).get("name"),
            "male_annual_income_10k_krw": customer.get(
                "male_annual_income_10k_krw"
            ),
            "female_annual_income_10k_krw": customer.get(
                "female_annual_income_10k_krw"
            ),
            "regional_average_annual_income_10k_krw": customer.get(
                "regional_average_annual_income_10k_krw"
            ),
        }
    else:
        compact["customer"] = None

    return compact


def _build_compact_insights(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []

    telecom_count = metrics.get("telecom_store_count")
    telecom_yoy = metrics.get("telecom_store_yoy_percent")
    if telecom_count is not None:
        insights.append(
            {
                "id": "Q-001",
                "title": "핸드폰 소매업 점포 현황",
                "evidence": (
                    f"선택 영역 내 핸드폰 소매업 {telecom_count}개, "
                    f"전년동월대비 {_percent_text(telecom_yoy)}"
                ),
                "metric_refs": [
                    "telecom_store_count",
                    "telecom_store_yoy_percent",
                ],
                "tags": ["telecom", "competition"],
            }
        )

    sales_amount = metrics.get("monthly_avg_sales_10k_krw")
    sales_transactions = metrics.get("monthly_avg_sales_transactions")
    if sales_amount is not None or sales_transactions is not None:
        insights.append(
            {
                "id": "Q-002",
                "title": "핸드폰 소매업 매출 특성",
                "evidence": (
                    f"업소당 월평균 매출액 {_value_text(sales_amount, '만원')}, "
                    f"월평균 매출건수 {_value_text(sales_transactions, '건')}; "
                    f"매출 집중 시간대는 "
                    f"{_label(TIME_LABELS, metrics.get('peak_sales_time_band'))}"
                ),
                "metric_refs": [
                    "monthly_avg_sales_10k_krw",
                    "monthly_avg_sales_transactions",
                    "peak_sales_time_band",
                ],
                "tags": ["sales", "telecom"],
            }
        )

    floating = metrics.get("daily_avg_floating_population")
    if floating is not None:
        insights.append(
            {
                "id": "Q-003",
                "title": "유동인구 특성",
                "evidence": (
                    f"일평균 유동인구 {floating}명, "
                    f"주요 성별·연령대는 "
                    f"{_label(GENDER_LABELS, metrics.get('dominant_floating_gender'))} / "
                    f"{_label(AGE_LABELS, metrics.get('dominant_floating_age'))}, "
                    f"최다 시간대는 "
                    f"{_label(TIME_LABELS, metrics.get('peak_floating_time_band'))}"
                ),
                "metric_refs": [
                    "daily_avg_floating_population",
                    "dominant_floating_gender",
                    "dominant_floating_age",
                    "peak_floating_time_band",
                ],
                "tags": ["population", "traffic"],
            }
        )

    households = metrics.get("household_count")
    facility = metrics.get("dominant_facility_type")
    if households is not None or facility is not None:
        insights.append(
            {
                "id": "Q-004",
                "title": "지역 생활기반",
                "evidence": (
                    f"세대수 {_value_text(households, '세대')}, "
                    f"주요 시설 유형 {_value_text(facility)}"
                ),
                "metric_refs": [
                    "household_count",
                    "dominant_facility_type",
                    "school_count",
                    "subway_station_count",
                    "bus_stop_count",
                ],
                "tags": ["area", "infrastructure"],
            }
        )

    customer = metrics.get("customer")
    if isinstance(customer, dict):
        insights.append(
            {
                "id": "Q-005",
                "title": "방문고객 특성",
                "evidence": (
                    "주요 방문 성별은 "
                    f"{_label(GENDER_LABELS, customer.get('dominant_visitor_gender'))}, "
                    f"남성 주요 라이프스타일은 "
                    f"{_value_text(customer.get('top_male_lifestyle'))}, "
                    f"여성 주요 라이프스타일은 "
                    f"{_value_text(customer.get('top_female_lifestyle'))}입니다."
                ),
                "metric_refs": [
                    "customer.dominant_visitor_gender",
                    "customer.top_male_lifestyle",
                    "customer.top_female_lifestyle",
                ],
                "tags": ["customer", "lifestyle"],
            }
        )

    return insights


def _build_compact_summary(
    admi_nm: str | None,
    radius_m: int,
    metrics: dict[str, Any],
) -> str:
    area_name = admi_nm or "선택 영역"
    parts: list[str] = []

    if metrics.get("telecom_store_count") is not None:
        parts.append(f"핸드폰 소매업 {metrics['telecom_store_count']}개")

    if metrics.get("monthly_avg_sales_10k_krw") is not None:
        parts.append(
            f"업소당 월평균 매출액 {metrics['monthly_avg_sales_10k_krw']}만원"
        )

    if metrics.get("daily_avg_floating_population") is not None:
        parts.append(
            f"일평균 유동인구 {metrics['daily_avg_floating_population']}명"
        )

    if metrics.get("household_count") is not None:
        parts.append(f"세대수 {metrics['household_count']}세대")

    if not parts:
        return f"{area_name} 반경 {radius_m}m 상세분석에서 핵심 지표를 추출하지 못했습니다."

    return f"{area_name} 반경 {radius_m}m 기준 " + ", ".join(parts) + "로 확인됐습니다."


def _build_sources(finished_at: str) -> list[dict[str, Any]]:
    return [
        {
            "source_id": "S-Q-001",
            "source_name": "소상공인365 상세분석",
            "source_type": "government",
            "source_url": "https://bigdata.sbiz.or.kr/",
            "published_at": None,
            "collected_at": finished_at,
        }
    ]


def run_quant_scout(request: SpotRequest, *, evidence_sink: Callable | None = None) -> ScoutResult:
    """Optionally retain this run's provider evidence internally; public output unchanged."""
    started_at = _now_iso()
    request_id = request.get("request_id", "unknown")

    store = request.get("store") or {}
    research = request.get("research") or {}

    lat = store.get("lat")
    lng = store.get("lng")
    radius_raw = research.get("radius_m", DEFAULT_RADIUS_M)

    query_context: dict[str, Any] = {
        "store_name": store.get("name"),
        "store_address": store.get("address"),
        "lat": lat,
        "lng": lng,
        "radius_m": radius_raw,
        "provider": "소상공인365",
    }

    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        store_address = store.get("address")

        if not isinstance(store_address, str) or not store_address.strip():
            return _failed_result(
                request,
                started_at,
                code="MISSING_LOCATION",
                message="store.lat/store.lng 좌표 또는 store.address 주소가 필요합니다.",
                query_context=query_context,
            )

        load_dotenv()
        kakao_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()

        if not kakao_api_key:
            return _failed_result(
                request,
                started_at,
                code="MISSING_KAKAO_REST_API_KEY",
                message="환경변수 KAKAO_REST_API_KEY가 없습니다.",
                query_context=query_context,
            )

        try:
            geocoded = resolve_address(
                store_address,
                api_key=kakao_api_key,
            )
        except KakaoGeocodeError as exc:
            return _failed_result(
                request,
                started_at,
                code="ADDRESS_GEOCODING_ERROR",
                message=str(exc),
                query_context=query_context,
            )

        lat = geocoded["lat"]
        lng = geocoded["lng"]

        query_context["lat"] = lat
        query_context["lng"] = lng
        query_context["coordinate_source"] = geocoded.get("coordinate_source")
        query_context["resolved_location"] = geocoded.get("resolved_name")
        query_context["resolved_address"] = geocoded.get("resolved_address")

    try:
        radius_m = int(radius_raw)
    except (TypeError, ValueError):
        return _failed_result(
            request,
            started_at,
            code="INVALID_RADIUS",
            message="research.radius_m은 정수여야 합니다.",
            query_context=query_context,
        )

    if radius_m <= 0:
        return _failed_result(
            request,
            started_at,
            code="INVALID_RADIUS",
            message="research.radius_m은 1 이상이어야 합니다.",
            query_context=query_context,
        )

    query_context["radius_m"] = radius_m

    load_dotenv()
    cert_key = os.getenv("SBIZ365_CERT_KEY", "").strip()

    if not cert_key:
        return _failed_result(
            request,
            started_at,
            code="MISSING_SBIZ365_CERT_KEY",
            message="환경변수 SBIZ365_CERT_KEY가 없습니다.",
            query_context=query_context,
        )

    try:
        collected = collect_sbiz365_reports(
            lat=float(lat),
            lng=float(lng),
            radius_m=radius_m,
            cert_key=cert_key,
            report_numbers=REPORT_NUMBERS,
        )
    except Sbiz365Error as exc:
        return _failed_result(
            request,
            started_at,
            code="SBIZ365_COLLECTION_ERROR",
            message=str(exc),
            query_context=query_context,
        )

    metrics, warnings, errors = _parse_reports(collected)

    parsed_core_sections = CORE_SECTIONS.intersection(metrics)
    missing_core_sections = CORE_SECTIONS.difference(metrics)

    if not parsed_core_sections:
        return _failed_result(
            request,
            started_at,
            code="SBIZ365_CORE_REPORTS_UNAVAILABLE",
            message="업종/매출/인구/지역현황 핵심 리포트를 파싱하지 못했습니다.",
            query_context={
                **query_context,
                "admi_cd": collected.get("admi_cd"),
                "admi_nm": collected.get("admi_nm"),
                "analysis_date": collected.get("analy_date"),
                "upjong_cd": collected.get("analysis", {}).get("upjong_cd"),
            },
        )

    partial_warning_codes = {
        "delivery_sales_payload_unparsed",
    }
    has_incomplete_parser_warning = any(
        warning.get("code") in partial_warning_codes
        for warning in warnings
        if isinstance(warning, dict)
    )

    status = (
        "partial"
        if missing_core_sections or errors or has_incomplete_parser_warning
        else "success"
    )

    if missing_core_sections:
        warnings.append(
            {
                "code": "quant_core_scope_partial",
                "message": (
                    "일부 핵심 상세분석 리포트를 파싱하지 못해 결과가 partial입니다: "
                    + ", ".join(sorted(missing_core_sections))
                ),
            }
        )

    compact_metrics = _build_compact_metrics(metrics)
    insights = _build_compact_insights(compact_metrics)
    # These statements only format API observations; preference/intent inferences
    # must use another claim kind and remain subject to semantic review.
    for insight in insights:
        insight["claim_kind"] = "public_api_observation"
        insight["source_ids"] = ["S-Q-001"]
    summary = _build_compact_summary(
        collected.get("admi_nm"),
        radius_m,
        compact_metrics,
    )
    finished_at = _now_iso()

    result: dict[str, Any] = {
        "schema_version": "0.1",
        "request_id": request_id,
        "module": "quant",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "query_context": {
            "radius_m": radius_m,
            "area_name": collected.get("admi_nm"),
            "store_address": query_context.get("store_address"),
            "lat": query_context.get("lat"),
            "lng": query_context.get("lng"),
            "analysis_date": collected.get("analy_date"),
            "upjong_cd": collected.get("analysis", {}).get("upjong_cd"),
        },
        "summary": summary,
        "metrics": compact_metrics,
        "insights": insights,
        "sources": _build_sources(finished_at),
        "warnings": warnings,
        "errors": errors,
    }

    if evidence_sink is not None:
        evidence_sink(deepcopy({
            "analysis": {name: collected.get("analysis", {}).get(name)
                         for name in ("lat", "lng", "radius_m", "upjong_cd")},
            "analy_date": collected.get("analy_date"),
            "reports": {number: {"html": report.get("html")}
                        for number, report in collected.get("reports", {}).items()
                        if number in (2, 3, 4, 6)},
        }))
    return cast(ScoutResult, result)
