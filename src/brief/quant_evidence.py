"""Read optional provider evidence without changing the Scout contract."""

from math import isclose

from src.scouts.quant_industry import parse_industry_report
from src.scouts.quant_sales import parse_sales_report
from src.scouts.quant_population import parse_population_report
from src.scouts.quant_area import parse_area_report


def read_quant_evidence(bundle, evidence):
    """Reject evidence from another location or inconsistent with Scout metrics."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get("analysis"), dict) or not isinstance(evidence.get("reports"), dict):
        raise ValueError("Quant 보조자료에는 analysis와 reports 객체가 필요합니다.")
    result = bundle.get("results", {}).get("quant", {})
    context = result.get("query_context", {})
    analysis = evidence.get("analysis", {})
    for name in ("lat", "lng"):
        actual, expected = analysis.get(name), context.get(name)
        if (isinstance(actual, bool) or isinstance(expected, bool)
                or not isinstance(actual, (int, float))
                or not isinstance(expected, (int, float))
                or not isclose(actual, expected, rel_tol=0, abs_tol=1e-8)):
            raise ValueError("Quant 보조자료의 조사 좌표가 결과와 다릅니다.")
    for name in ("radius_m", "upjong_cd"):
        if analysis.get(name) != context.get(name):
            raise ValueError("Quant 보조자료의 반경 또는 업종이 결과와 다릅니다.")
    if evidence.get("analy_date") != context.get("analysis_date"):
        raise ValueError("Quant 보조자료의 분석 생성일이 결과와 다릅니다.")

    sections = {}
    parsers = {2: ("industry", parse_industry_report),
               3: ("sales", parse_sales_report),
               4: ("population", parse_population_report),
               6: ("area", parse_area_report)}
    reports = evidence.get("reports", {})
    for number, (name, parser) in parsers.items():
        report = reports.get(str(number), reports.get(number, {}))
        if report.get("html"):
            sections[name] = parser(report["html"])

    anchors = {
        "industry": {"telecom_store_count": "latest_store_count"},
        "sales": {"monthly_avg_sales_10k_krw": "latest_monthly_average_sales_amount_10k_krw",
                  "monthly_avg_sales_transactions": "latest_monthly_average_sales_transactions"},
        "population": {"daily_avg_floating_population": "latest_monthly_daily_flow_population",
                       "resident_population": "latest_resident_population_from_trend",
                       "worker_population": "latest_worker_population_from_trend"},
        "area": {"household_count": "latest_households"},
    }
    metrics = result.get("metrics", {})
    for section, names in anchors.items():
        if section not in sections:
            continue
        derived = sections[section].get("derived_selected_area", {})
        for metric, field in names.items():
            if metrics.get(metric) != derived.get(field):
                raise ValueError(f"Quant 보조자료의 {metric} 값이 결과와 다릅니다.")
    return sections
