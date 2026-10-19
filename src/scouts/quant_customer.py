"""SBIZ365 고객특성(sang_gwon7.sg) HTML parser.

파싱 대상:
- 방문고객 성별 비율
- 신규/단골 고객 비율
- 남/여 주요 라이프스타일
- 방문고객 연 평균소득
- 성별/연령별 소비 매출액
- 리포트 분석결과 문구

데이터가 없는 응답도 실패시키지 않고 unavailable 상태로 보존한다.
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


AGE_FIELD_MAP = {
    "gen20CnsmpAmt": "20s",
    "gen30CnsmpAmt": "30s",
    "gen40CnsmpAmt": "40s",
    "gen50CnsmpAmt": "50s",
    "gen60OverCnsmpAmt": "60_plus",
}

GENDER_KEY_MAP = {
    "남성": "male",
    "여성": "female",
}

CUSTOMER_TYPE_KEY_MAP = {
    "신규": "new",
    "단골": "loyal",
}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_text(fragment: str) -> str:
    parser = _TextParser()
    parser.feed(fragment)
    return re.sub(
        r"\s+",
        " ",
        unescape("".join(parser.parts)),
    ).strip()


def _extract_js_string(
    html_text: str,
    variable_name: str,
) -> str | None:
    match = re.search(
        rf"\bvar\s+{re.escape(variable_name)}\s*=\s*"
        r'(["\'])(.*?)\1\s*;',
        html_text,
        flags=re.S,
    )
    return match.group(2).strip() if match else None


def _to_number(value: str | None) -> int | float | None:
    if value is None:
        return None

    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None

    try:
        number = float(cleaned)
    except ValueError:
        return None

    return int(number) if number.is_integer() else number


def _parse_java_map_list(value: str | None) -> list[dict[str, Any]]:
    """'[{a=1, b=x}, {a=2, b=y}]' 형태의 SBIZ365 문자열을 파싱한다."""
    if value is None:
        return []

    stripped = value.strip()
    if not stripped or stripped == "[]":
        return []

    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []

    body = stripped[1:-1].strip()
    if not body:
        return []

    records = re.findall(r"\{(.*?)\}", body, flags=re.S)
    parsed: list[dict[str, Any]] = []

    for record in records:
        item: dict[str, Any] = {}
        for part in record.split(","):
            if "=" not in part:
                continue
            key, raw = part.split("=", 1)
            key = key.strip()
            raw = raw.strip()

            numeric = _to_number(raw)
            item[key] = numeric if numeric is not None else raw

        if item:
            parsed.append(item)

    return parsed


def _extract_number_assignment(
    html_text: str,
    variable_name: str,
) -> int | float | None:
    match = re.search(
        rf"\bvar\s+{re.escape(variable_name)}\s*=\s*"
        r'Number\s*\(\s*["\']([^"\']*)["\']\s*\)\s*;',
        html_text,
        flags=re.S,
    )
    return _to_number(match.group(1)) if match else None


def _extract_annual_income(
    html_text: str,
) -> dict[str, int | float | None]:
    male_match = re.search(
        r'class=["\'][^"\']*\bmaleRatio\b[^"\']*["\'][^>]*>'
        r'.*?남성\s*<span>\s*([\d,]+)\s*만원\s*</span>',
        html_text,
        flags=re.I | re.S,
    )
    female_match = re.search(
        r'class=["\'][^"\']*\bfemaleRatio\b[^"\']*["\'][^>]*>'
        r'.*?여성\s*<span>\s*([\d,]+)\s*만원\s*</span>',
        html_text,
        flags=re.I | re.S,
    )

    regional_match = re.search(
        r"지역\s*내\s*연평균\s*소득\s*\(\s*([\d,]+)\s*만원\s*\)",
        _visible_text(html_text),
    )

    return {
        "male_annual_income_10k_krw": (
            _to_number(male_match.group(1))
            if male_match
            else None
        ),
        "female_annual_income_10k_krw": (
            _to_number(female_match.group(1))
            if female_match
            else None
        ),
        "regional_average_annual_income_10k_krw": (
            _to_number(regional_match.group(1))
            if regional_match
            else None
        ),
    }


def _extract_analysis_texts(
    html_text: str,
) -> list[str]:
    blocks = re.findall(
        r'<dl\b[^>]*class=["\'][^"\']*\banalyResult\b[^"\']*["\'][^>]*>'
        r"(.*?)</dl>",
        html_text,
        flags=re.I | re.S,
    )
    texts: list[str] = []
    for block in blocks:
        value = _visible_text(block)
        if value:
            texts.append(value)
    return texts


def _normalize_gender(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for record in records:
        label = str(record.get("genNm", "")).strip()
        key = GENDER_KEY_MAP.get(label)
        if not key:
            continue

        result[key] = {
            "label": label,
            "count": record.get("popnum"),
            "share_pct": record.get("popnumRate"),
        }

    return result


def _normalize_customer_type(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for record in records:
        label = str(
            record.get("newCstmCustNm", "")
        ).strip()
        key = CUSTOMER_TYPE_KEY_MAP.get(label)
        if not key:
            continue

        result[key] = {
            "label": label,
            "count": record.get("newCstmCustCnt"),
            "share_pct": record.get("newCstmCntRate"),
        }

    return result


def _normalize_lifestyle(
    records: list[dict[str, Any]],
    *,
    gender: str,
) -> list[dict[str, Any]]:
    if gender == "male":
        name_key = "maleCustHbbNm"
        count_key = "maleCustCnt"
        rate_key = "maleCustRate"
    else:
        name_key = "femaleCustHbbNm"
        count_key = "femaleCustCnt"
        rate_key = "femaleCustRate"

    result: list[dict[str, Any]] = []

    for record in records:
        name = record.get(name_key)
        if name is None:
            continue

        result.append(
            {
                "name": str(name),
                "count": record.get(count_key),
                "share_pct": record.get(rate_key),
            }
        )

    return result


def _normalize_sex_age_sales(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for record in records:
        gender_label = str(
            record.get("cnsmpGenNm", "")
        ).strip()
        gender_key = GENDER_KEY_MAP.get(gender_label)
        if not gender_key:
            continue

        values: dict[str, Any] = {}
        for source_key, age_key in AGE_FIELD_MAP.items():
            values[age_key] = record.get(source_key)

        result[gender_key] = {
            "label": gender_label,
            "unit": "10k_krw",
            "by_age": values,
        }

    return result


def _dominant_dict_key(
    values: dict[str, dict[str, Any]],
    field: str,
) -> str | None:
    candidates = [
        (key, data.get(field))
        for key, data in values.items()
        if isinstance(data.get(field), (int, float))
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: float(item[1]),
    )[0]


def _top_lifestyle(
    values: list[dict[str, Any]],
    *,
    exclude_other: bool,
) -> dict[str, Any] | None:
    candidates = [
        item
        for item in values
        if isinstance(item.get("share_pct"), (int, float))
        and (
            not exclude_other
            or str(item.get("name")) != "기타"
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: float(item["share_pct"]),
    )


def _dominant_age(
    sales: dict[str, Any] | None,
) -> str | None:
    if not sales:
        return None

    by_age = sales.get("by_age", {})
    candidates = [
        (age, value)
        for age, value in by_age.items()
        if isinstance(value, (int, float))
    ]
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: float(item[1]),
    )[0]


def _sum_share(
    values: list[int | float | None],
) -> float | None:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
    ]
    if not numeric:
        return None
    return round(sum(numeric), 1)


def parse_customer_report(
    html_text: str,
) -> dict[str, Any]:
    raw_strings = {
        "visitor_gender_ratio": _extract_js_string(
            html_text,
            "vstCustSexRt",
        ),
        "new_vs_loyal_customer_ratio": _extract_js_string(
            html_text,
            "vstCustNewCstmRt",
        ),
        "male_major_lifestyle": _extract_js_string(
            html_text,
            "maleVstCustMjrLife",
        ),
        "female_major_lifestyle": _extract_js_string(
            html_text,
            "femaleVstCustMjrLife",
        ),
        "sex_age_sales_amount": _extract_js_string(
            html_text,
            "vstCustSexAgeSlamt",
        ),
    }

    parsed_raw = {
        key: _parse_java_map_list(value)
        for key, value in raw_strings.items()
    }

    gender = _normalize_gender(
        parsed_raw["visitor_gender_ratio"]
    )
    customer_type = _normalize_customer_type(
        parsed_raw["new_vs_loyal_customer_ratio"]
    )
    male_lifestyle = _normalize_lifestyle(
        parsed_raw["male_major_lifestyle"],
        gender="male",
    )
    female_lifestyle = _normalize_lifestyle(
        parsed_raw["female_major_lifestyle"],
        gender="female",
    )
    sex_age_sales = _normalize_sex_age_sales(
        parsed_raw["sex_age_sales_amount"]
    )
    annual_income = _extract_annual_income(
        html_text
    )
    analysis_texts = _extract_analysis_texts(
        html_text
    )

    section_availability = {
        "visitor_gender_ratio": bool(gender),
        "new_vs_loyal_customer_ratio": bool(
            customer_type
        ),
        "male_major_lifestyle": bool(
            male_lifestyle
        ),
        "female_major_lifestyle": bool(
            female_lifestyle
        ),
        "annual_income": any(
            value is not None
            for value in annual_income.values()
        ),
        "sex_age_sales_amount": bool(
            sex_age_sales
        ),
    }

    has_customer_data = any(
        section_availability.values()
    )

    warnings: list[dict[str, Any]] = []

    if not has_customer_data:
        warnings.append(
            {
                "code": "customer_data_unavailable",
                "message": (
                    "이 상세분석 응답에는 고객특성 데이터가 제공되지 않았습니다. "
                    "빈 값을 임의로 추정하지 않고 그대로 보존합니다."
                ),
            }
        )

    gender_total = _sum_share(
        [
            value.get("share_pct")
            for value in gender.values()
        ]
    )
    if (
        gender_total is not None
        and abs(gender_total - 100.0) > 0.2
    ):
        warnings.append(
            {
                "code": "customer_gender_share_mismatch",
                "message": (
                    "방문고객 성별 비율의 합이 100%와 다릅니다. "
                    "원문 값을 그대로 보존했습니다."
                ),
                "share_total": gender_total,
            }
        )

    customer_type_total = _sum_share(
        [
            value.get("share_pct")
            for value in customer_type.values()
        ]
    )
    if (
        customer_type_total is not None
        and abs(customer_type_total - 100.0) > 0.2
    ):
        warnings.append(
            {
                "code": "customer_new_loyal_share_mismatch",
                "message": (
                    "신규/단골 고객 비율의 합이 100%와 다릅니다. "
                    "원문 값을 그대로 보존했습니다."
                ),
                "share_total": customer_type_total,
            }
        )

    # 템플릿이 차트에 전달한 값과 원본 payload가 맞는지 교차 검증한다.
    chart_gender = {
        "male": _extract_number_assignment(
            html_text,
            "malePopnumRate",
        ),
        "female": _extract_number_assignment(
            html_text,
            "femalePopnumRate",
        ),
    }
    chart_customer_type = {
        "new": _extract_number_assignment(
            html_text,
            "newCstmCntRate",
        ),
        "loyal": _extract_number_assignment(
            html_text,
            "cstmCntRate",
        ),
    }

    for key, chart_value in chart_gender.items():
        raw_value = gender.get(key, {}).get(
            "share_pct"
        )
        if (
            chart_value is not None
            and raw_value is not None
            and float(chart_value)
            != float(raw_value)
        ):
            warnings.append(
                {
                    "code": "customer_gender_chart_mismatch",
                    "message": (
                        "성별 비율 원본 payload와 차트 값이 다릅니다. "
                        "원본 값을 그대로 보존했습니다."
                    ),
                    "gender": key,
                    "raw_value": raw_value,
                    "chart_value": chart_value,
                }
            )

    for key, chart_value in chart_customer_type.items():
        raw_value = customer_type.get(
            key,
            {},
        ).get("share_pct")
        if (
            chart_value is not None
            and raw_value is not None
            and float(chart_value)
            != float(raw_value)
        ):
            warnings.append(
                {
                    "code": "customer_type_chart_mismatch",
                    "message": (
                        "신규/단골 원본 payload와 차트 값이 다릅니다. "
                        "원본 값을 그대로 보존했습니다."
                    ),
                    "customer_type": key,
                    "raw_value": raw_value,
                    "chart_value": chart_value,
                }
            )

    dominant_gender = _dominant_dict_key(
        gender,
        "share_pct",
    )
    dominant_customer_type = _dominant_dict_key(
        customer_type,
        "share_pct",
    )

    top_male_lifestyle = _top_lifestyle(
        male_lifestyle,
        exclude_other=True,
    )
    top_female_lifestyle = _top_lifestyle(
        female_lifestyle,
        exclude_other=True,
    )

    male_age = _dominant_age(
        sex_age_sales.get("male")
    )
    female_age = _dominant_age(
        sex_age_sales.get("female")
    )

    overall_candidates: list[
        tuple[str, str, float]
    ] = []
    for gender_key, payload in sex_age_sales.items():
        for age_key, value in payload.get(
            "by_age",
            {},
        ).items():
            if isinstance(value, (int, float)):
                overall_candidates.append(
                    (
                        gender_key,
                        age_key,
                        float(value),
                    )
                )

    overall_peak = (
        max(
            overall_candidates,
            key=lambda item: item[2],
        )
        if overall_candidates
        else None
    )

    return {
        "schema_version": "sbiz365.customer.v0.2",
        "source": {
            "report": "sang_gwon7.sg",
            "note": (
                "SBIZ365 inline JavaScript payload와 HTML 표시값을 "
                "JavaScript 실행 없이 정규화했습니다."
            ),
        },
        "section_availability": section_availability,
        "customer_metrics": {
            "visitor_gender_ratio": {
                "unit": "percent",
                "values": gender,
            },
            "new_vs_loyal_customer_ratio": {
                "unit": "percent",
                "values": customer_type,
                "loyal_definition": (
                    "월 방문 횟수 3회 이상 방문자"
                ),
            },
            "major_lifestyle": {
                "unit": "percent",
                "male": male_lifestyle,
                "female": female_lifestyle,
            },
            "annual_income": {
                "unit": "10k_krw_per_year",
                **annual_income,
            },
            "sex_age_sales_amount": {
                "unit": "10k_krw",
                "values": sex_age_sales,
            },
        },
        "reported_analysis": {
            "texts": analysis_texts,
        },
        "raw_payloads": raw_strings,
        "derived_selected_area": {
            "has_customer_data": has_customer_data,
            "available_sections": [
                key
                for key, available
                in section_availability.items()
                if available
            ],
            "available_section_count": sum(
                1
                for available
                in section_availability.values()
                if available
            ),
            "dominant_visitor_gender": (
                dominant_gender
            ),
            "dominant_customer_type": (
                dominant_customer_type
            ),
            "top_male_lifestyle_excluding_other": (
                top_male_lifestyle
            ),
            "top_female_lifestyle_excluding_other": (
                top_female_lifestyle
            ),
            "male_annual_income_10k_krw": (
                annual_income[
                    "male_annual_income_10k_krw"
                ]
            ),
            "female_annual_income_10k_krw": (
                annual_income[
                    "female_annual_income_10k_krw"
                ]
            ),
            "regional_average_annual_income_10k_krw": (
                annual_income[
                    "regional_average_annual_income_10k_krw"
                ]
            ),
            "dominant_male_sales_age": male_age,
            "dominant_female_sales_age": female_age,
            "overall_peak_sales_gender": (
                overall_peak[0]
                if overall_peak
                else None
            ),
            "overall_peak_sales_age": (
                overall_peak[1]
                if overall_peak
                else None
            ),
            "overall_peak_sales_amount_10k_krw": (
                overall_peak[2]
                if overall_peak
                else None
            ),
        },
        "warnings": warnings,
    }


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "사용법: python quant_customer.py "
            "<sang_gwon7.raw.html> [output.json]",
            file=sys.stderr,
        )
        return 1

    input_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else input_path.with_suffix(
            ".normalized.json"
        )
    )

    html_text = input_path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    result = parse_customer_report(
        html_text
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    derived = result["derived_selected_area"]
    metrics = result["customer_metrics"]

    print("고객특성 파싱 성공")
    print(
        "고객특성 데이터 존재: "
        f"{derived['has_customer_data']}"
    )

    if derived["has_customer_data"]:
        genders = metrics[
            "visitor_gender_ratio"
        ]["values"]
        male_share = genders.get(
            "male",
            {},
        ).get("share_pct")
        female_share = genders.get(
            "female",
            {},
        ).get("share_pct")
        print(
            "방문고객 성별 비율: "
            f"남성 {male_share}% / "
            f"여성 {female_share}%"
        )

        types = metrics[
            "new_vs_loyal_customer_ratio"
        ]["values"]
        new_share = types.get(
            "new",
            {},
        ).get("share_pct")
        loyal_share = types.get(
            "loyal",
            {},
        ).get("share_pct")
        print(
            "신규/단골 비율: "
            f"신규 {new_share}% / "
            f"단골 {loyal_share}%"
        )

        male_life = derived[
            "top_male_lifestyle_excluding_other"
        ]
        female_life = derived[
            "top_female_lifestyle_excluding_other"
        ]
        print(
            "남성 주요 라이프스타일: "
            f"{male_life['name']} "
            f"{male_life['share_pct']}%"
            if male_life
            else "남성 주요 라이프스타일: 확인 불가"
        )
        print(
            "여성 주요 라이프스타일: "
            f"{female_life['name']} "
            f"{female_life['share_pct']}%"
            if female_life
            else "여성 주요 라이프스타일: 확인 불가"
        )

        print(
            "방문고객 연 평균소득: "
            f"남성 "
            f"{derived['male_annual_income_10k_krw']}만원 / "
            f"여성 "
            f"{derived['female_annual_income_10k_krw']}만원"
        )

        print(
            "성·연령별 소비 매출액 최고: "
            f"{derived['overall_peak_sales_gender']} / "
            f"{derived['overall_peak_sales_age']} / "
            f"{derived['overall_peak_sales_amount_10k_krw']}만원"
        )

    if result["warnings"]:
        print()
        print("경고:")
        for warning in result["warnings"]:
            print(
                f"- {warning['code']}: "
                f"{warning['message']}"
            )

    print()
    print(f"저장 위치: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
