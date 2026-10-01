"""SBIZ365 업종분석(sang_gwon2.sg) HTML parser.

외부 패키지 없이 HTML/JavaScript 응답을 정규화한다.
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


BUSINESS_AGE_KEYS = (
    ("under_1_year", "1년 미만"),
    ("1_to_2_years", "1년~2년"),
    ("2_to_3_years", "2년~3년"),
    ("3_to_5_years", "3년~5년"),
    ("5_plus_years", "5년 이상"),
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()


def _number(value: str) -> int | float | None:
    cleaned = value.replace(",", "").replace("%", "").strip()
    if not cleaned or cleaned in {"-", "null", "None"}:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return number


def _signed_percent(cell_html: str) -> float | int | None:
    value = _number(_text(cell_html))
    if value is None:
        return None

    classes = " ".join(
        re.findall(r'class\s*=\s*["\']([^"\']+)["\']', cell_html, flags=re.I)
    ).lower()

    numeric = float(value)
    if "down" in classes and numeric > 0:
        numeric = -numeric
    elif "up" in classes and numeric < 0:
        numeric = abs(numeric)

    return int(numeric) if numeric.is_integer() else numeric


def _period_iso(korean_period: str | None) -> str | None:
    if not korean_period:
        return None
    match = re.search(r"(\d{4})년\s*(\d{1,2})월", korean_period)
    if not match:
        return korean_period.strip()
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"


def _extract_table_rows(html_text: str) -> list[list[dict[str, Any]]]:
    table_match = re.search(
        r"<table\b[^>]*>.*?</table>",
        html_text,
        flags=re.I | re.S,
    )
    if not table_match:
        return []

    rows: list[list[dict[str, Any]]] = []
    for row_html in re.findall(
        r"<tr\b[^>]*>(.*?)</tr>",
        table_match.group(0),
        flags=re.I | re.S,
    ):
        cells: list[dict[str, Any]] = []
        for tag, cell_html in re.findall(
            r"<(th|td)\b[^>]*>(.*?)</\1>",
            row_html,
            flags=re.I | re.S,
        ):
            cells.append(
                {
                    "tag": tag.lower(),
                    "text": _text(cell_html),
                    "html": cell_html,
                }
            )
        if cells:
            rows.append(cells)
    return rows


def _extract_store_count_trend(html_text: str) -> dict[str, Any]:
    rows = _extract_table_rows(html_text)
    if not rows:
        raise ValueError("업소수 추이 표를 찾지 못했습니다.")

    header = [cell["text"] for cell in rows[0]]
    if len(header) < 3 or header[0] != "지역" or header[1] != "구분":
        raise ValueError("업소수 추이 표 헤더 형식을 인식하지 못했습니다.")

    periods = header[2:]
    regions: dict[str, dict[str, Any]] = {}
    previous_region: str | None = None

    for row in rows[1:]:
        texts = [cell["text"] for cell in row]
        if not texts:
            continue

        if texts[0] == "증감률":
            if previous_region is None:
                continue
            changes = [
                _signed_percent(cell["html"])
                for cell in row[1:]
            ]
            regions[previous_region]["month_over_month_change_percent"] = changes
            continue

        if len(texts) < 2 or texts[1] != "업소수":
            continue

        region_name = texts[0]
        counts = [_number(cell["text"]) for cell in row[2:]]
        regions[region_name] = {
            "counts": counts,
        }
        previous_region = region_name

    for region_data in regions.values():
        counts = region_data.get("counts", [])
        region_data["latest_count"] = counts[-1] if counts else None

    return {
        "periods": periods,
        "regions": regions,
    }


def _extract_call_values(html_text: str, function_name: str) -> list[int | float | None]:
    match = re.search(
        rf"\b{re.escape(function_name)}\s*\((.*?)\)\s*;",
        html_text,
        flags=re.S,
    )
    if not match:
        return []

    raw_args = match.group(1)
    number_strings = re.findall(
        r'Number\s*\(\s*["\']([^"\']*)["\']\s*\)',
        raw_args,
    )
    return [_number(value) for value in number_strings]


def _extract_business_age(html_text: str) -> dict[str, Any]:
    caption_match = re.search(
        r'<[^>]*class=["\'][^"\']*\bcaption\b[^"\']*["\'][^>]*>'
        r'(.*?)</[^>]+>',
        html_text,
        flags=re.I | re.S,
    )
    caption = _text(caption_match.group(1)) if caption_match else ""

    context: dict[str, Any] = {
        "raw_caption": caption or None,
        "region": None,
        "industry_group": None,
        "reference_period": None,
    }

    caption_info = re.search(
        r"업력정보\s*:\s*(.+?),\s*(.+?),\s*(\d{4}년\s*\d{1,2}월)\s*기준",
        caption,
    )
    if caption_info:
        context["region"] = caption_info.group(1).strip()
        context["industry_group"] = caption_info.group(2).strip()
        context["reference_period"] = _period_iso(caption_info.group(3))

    period_by_chart_id: dict[str, str] = {}
    for title, chart_id in re.findall(
        r'<p\b[^>]*class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>'
        r'(.*?)</p>\s*'
        r'<div\b[^>]*class=["\'][^"\']*\bdata\b[^"\']*["\'][^>]*'
        r'id=["\']([^"\']+)["\'][^>]*>',
        html_text,
        flags=re.I | re.S,
    ):
        period_by_chart_id[chart_id] = _period_iso(_text(title)) or _text(title)

    current_values = _extract_call_values(html_text, "storeOC")
    previous_values = _extract_call_values(html_text, "storeOCPrev")

    def snapshot(chart_id: str, values: list[int | float | None]) -> dict[str, Any]:
        mapped = {
            key: value
            for (key, _label), value in zip(BUSINESS_AGE_KEYS, values)
        }
        numeric_values = [
            float(value)
            for value in mapped.values()
            if isinstance(value, (int, float))
        ]
        total = sum(numeric_values) if numeric_values else None
        if total is not None and float(total).is_integer():
            total = int(total)
        return {
            "period": period_by_chart_id.get(chart_id),
            "values": mapped,
            "total": total,
        }

    return {
        "context": context,
        "categories": [
            {"key": key, "label": label}
            for key, label in BUSINESS_AGE_KEYS
        ],
        "previous": snapshot("storeOCPrev", previous_values),
        "current": snapshot("storeOC", current_values),
    }


def _extract_analysis_result(html_text: str) -> dict[str, Any]:
    match = re.search(
        r'<dl\b[^>]*class=["\'][^"\']*\banalyResult\b[^"\']*["\'][^>]*>'
        r'(.*?)</dl>',
        html_text,
        flags=re.I | re.S,
    )
    if not match:
        return {
            "text": None,
            "selected_area": {},
            "new_business": {},
        }

    block = match.group(1)
    analysis_text = _text(block)

    selected: dict[str, Any] = {}
    selected_match = re.search(
        r"선택\s*영역.*?"
        r"<strong[^>]*>\s*([^<]+?)\s*</strong>"
        r".*?전년동월대비\s*"
        r".*?<strong[^>]*>\s*(-?[\d,.]+)%\s*(많습니다|적습니다|증가했습니다|감소했습니다)",
        block,
        flags=re.I | re.S,
    )
    if selected_match:
        rate = float(selected_match.group(2).replace(",", ""))
        direction_word = selected_match.group(3)
        if direction_word in {"적습니다", "감소했습니다"} and rate > 0:
            rate = -rate
        selected = {
            "industry": _text(selected_match.group(1)),
            "year_over_year_change_percent": rate,
            "direction_text": direction_word,
        }

    new_business: dict[str, Any] = {}
    strong_matches = list(
        re.finditer(
            r"<strong[^>]*>\s*([^<]+?)\s*</strong>",
            block,
            flags=re.I | re.S,
        )
    )
    for index, strong_match in enumerate(strong_matches[:-1]):
        next_strong = strong_matches[index + 1]
        between = _text(block[strong_match.end():next_strong.start()])
        if not re.search(
            r"^\s*의\s*1년\s*미만\s*신규\s*창업\s*업소\s*수는\s*전반기\s*대비",
            between,
        ):
            continue

        value_text = _text(next_strong.group(1))
        value_match = re.search(
            r"([\d,.]+)개\s*(많습니다|적습니다|증가했습니다|감소했습니다)",
            value_text,
        )
        if not value_match:
            continue

        count = int(float(value_match.group(1).replace(",", "")))
        direction_word = value_match.group(2)
        if direction_word in {"적습니다", "감소했습니다"}:
            count = -abs(count)
        else:
            count = abs(count)

        new_business = {
            "region": _text(strong_match.group(1)),
            "age_band": "under_1_year",
            "half_year_change_count": count,
            "direction_text": direction_word,
        }
        break

    return {
        "text": analysis_text or None,
        "selected_area": selected,
        "new_business": new_business,
    }


def _find_year_ago(periods: list[str], counts: list[Any]) -> tuple[str | None, Any]:
    if not periods or not counts or len(periods) != len(counts):
        return None, None

    latest = periods[-1]
    match = re.fullmatch(r"(\d{2})\.(\d{2})", latest)
    if not match:
        return None, None

    previous_year = f"{(int(match.group(1)) - 1) % 100:02d}.{match.group(2)}"
    try:
        index = periods.index(previous_year)
    except ValueError:
        return None, None
    return previous_year, counts[index]


def parse_industry_report(html_text: str) -> dict[str, Any]:
    store_count = _extract_store_count_trend(html_text)
    business_age = _extract_business_age(html_text)
    analysis_result = _extract_analysis_result(html_text)

    warnings: list[dict[str, Any]] = []

    regions = store_count.get("regions", {})
    selected = regions.get("선택 영역", {})
    selected_counts = selected.get("counts", [])
    periods = store_count.get("periods", [])

    latest_count = selected_counts[-1] if selected_counts else None
    year_ago_period, year_ago_count = _find_year_ago(periods, selected_counts)

    computed_yoy: float | None = None
    if (
        isinstance(latest_count, (int, float))
        and isinstance(year_ago_count, (int, float))
        and year_ago_count != 0
    ):
        computed_yoy = round(
            (float(latest_count) - float(year_ago_count))
            / float(year_ago_count)
            * 100,
            1,
        )

    monthly_changes = selected.get("month_over_month_change_percent", [])
    latest_mom = monthly_changes[-1] if monthly_changes else None

    reported_yoy = (
        analysis_result.get("selected_area", {})
        .get("year_over_year_change_percent")
    )

    if (
        computed_yoy is not None
        and isinstance(reported_yoy, (int, float))
        and abs(computed_yoy - float(reported_yoy)) > 0.2
    ):
        warnings.append(
            {
                "code": "industry_yoy_mismatch",
                "message": (
                    "업소수 시계열로 계산한 전년동월대비 증감률과 "
                    "분석결과 문구의 증감률이 다릅니다. 원문 값을 모두 보존했습니다."
                ),
                "computed_percent": computed_yoy,
                "reported_percent": reported_yoy,
            }
        )

    current_age = business_age.get("current", {}).get("values", {})
    previous_age = business_age.get("previous", {}).get("values", {})
    current_new = current_age.get("under_1_year")
    previous_new = previous_age.get("under_1_year")

    computed_new_change: int | float | None = None
    if isinstance(current_new, (int, float)) and isinstance(previous_new, (int, float)):
        computed_new_change = current_new - previous_new

    reported_new_change = (
        analysis_result.get("new_business", {})
        .get("half_year_change_count")
    )
    if (
        isinstance(computed_new_change, (int, float))
        and isinstance(reported_new_change, (int, float))
        and float(computed_new_change) != float(reported_new_change)
    ):
        warnings.append(
            {
                "code": "new_business_change_mismatch",
                "message": (
                    "업력 차트로 계산한 1년 미만 업소 증감과 "
                    "분석결과 문구의 증감이 다릅니다. 원문 값을 모두 보존했습니다."
                ),
                "computed_count": computed_new_change,
                "reported_count": reported_new_change,
            }
        )

    latest_comparison = {
        region_name: region_data.get("latest_count")
        for region_name, region_data in regions.items()
    }

    return {
        "schema_version": "sbiz365.industry.v0.1",
        "source": {
            "report": "sang_gwon2.sg",
            "note": "HTML/inline JavaScript response normalized without executing JavaScript",
        },
        "store_count_trend": store_count,
        "business_age": business_age,
        "analysis_result": analysis_result,
        "derived_selected_area": {
            "latest_period": periods[-1] if periods else None,
            "latest_store_count": latest_count,
            "year_ago_period": year_ago_period,
            "year_ago_store_count": year_ago_count,
            "year_over_year_change_percent_computed": computed_yoy,
            "year_over_year_change_percent_reported": reported_yoy,
            "latest_month_over_month_change_percent": latest_mom,
            "latest_comparison_counts": latest_comparison,
            "business_age_current_period": business_age.get("current", {}).get("period"),
            "business_age_previous_period": business_age.get("previous", {}).get("period"),
            "under_1_year_current_count": current_new,
            "under_1_year_previous_count": previous_new,
            "under_1_year_half_year_change_computed": computed_new_change,
            "under_1_year_half_year_change_reported": reported_new_change,
        },
        "warnings": warnings,
    }


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "사용법: python quant_industry.py <sang_gwon2.raw.html> [output.json]",
            file=sys.stderr,
        )
        return 1

    input_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else input_path.with_suffix(".normalized.json")
    )

    html_text = input_path.read_text(encoding="utf-8", errors="replace")
    result = parse_industry_report(html_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    derived = result["derived_selected_area"]
    age_context = result["business_age"]["context"]

    print("업종분석 파싱 성공")
    print(f"최신 업소수: {derived['latest_store_count']}")
    print(
        "전년동월대비 업소수 증감률: "
        f"{derived['year_over_year_change_percent_reported']}%"
    )
    print(
        "업력 기준: "
        f"{age_context.get('region')} / {age_context.get('industry_group')}"
    )
    print(
        "1년 미만 업소수: "
        f"{derived['under_1_year_previous_count']} -> "
        f"{derived['under_1_year_current_count']}"
    )

    if result["warnings"]:
        print("\\n경고:")
        for warning in result["warnings"]:
            print(f"- {warning['code']}: {warning['message']}")

    print(f"\\n저장 위치: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
