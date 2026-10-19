"""SBIZ365 매출분석(sang_gwon3.sg) HTML parser.

리포트의 표와 분석결과 문구를 JavaScript 실행 없이 정규화한다.
금액 단위는 원문 표 기준 '만원'이다.
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DAY_KEYS = (
    ("weekday", "주중"),
    ("weekend", "주말"),
    ("mon", "월"),
    ("tue", "화"),
    ("wed", "수"),
    ("thu", "목"),
    ("fri", "금"),
    ("sat", "토"),
    ("sun", "일"),
)

TIME_KEYS = (
    ("05_09", "05~09시"),
    ("09_12", "09~12시"),
    ("12_14", "12~14시"),
    ("14_18", "14~18시"),
    ("18_23", "18~23시"),
    ("23_05", "23~05시"),
)

DEMOGRAPHIC_KEYS = (
    ("male", "남성"),
    ("female", "여성"),
    ("teens", "10대"),
    ("20s", "20대"),
    ("30s", "30대"),
    ("40s", "40대"),
    ("50s", "50대"),
    ("60_plus", "60대이상"),
)

DAY_REPORTED_MAP = {
    "월요일": "mon",
    "화요일": "tue",
    "수요일": "wed",
    "목요일": "thu",
    "금요일": "fri",
    "토요일": "sat",
    "일요일": "sun",
}

GENDER_REPORTED_MAP = {
    "남성": "male",
    "여성": "female",
}

AGE_REPORTED_MAP = {
    "10대": "teens",
    "20대": "20s",
    "30대": "30s",
    "40대": "40s",
    "50대": "50s",
    "60대이상": "60_plus",
    "60대 이상": "60_plus",
}


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


def _extract_table_after_marker(html_text: str, marker: str) -> str:
    marker_pos = html_text.find(marker)
    if marker_pos < 0:
        raise ValueError(f"표 제목을 찾지 못했습니다: {marker}")

    match = re.search(
        r"<table\b[^>]*>.*?</table>",
        html_text[marker_pos:],
        flags=re.I | re.S,
    )
    if not match:
        raise ValueError(f"표를 찾지 못했습니다: {marker}")
    return match.group(0)


class _TableRowsParser(HTMLParser):
    """Malformed HTML도 최대한 보존해서 표 셀을 읽는다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict[str, Any]]] = []
        self.current_row: list[dict[str, Any]] | None = None
        self.current_cell: dict[str, Any] | None = None
        self.cell_text_parts: list[str] = []
        self.cell_html_parts: list[str] = []

    def _finish_cell(self) -> None:
        if self.current_cell is None or self.current_row is None:
            return
        text = re.sub(r"\s+", " ", "".join(self.cell_text_parts)).strip()
        self.current_cell["text"] = unescape(text)
        self.current_cell["html"] = "".join(self.cell_html_parts)
        self.current_row.append(self.current_cell)
        self.current_cell = None
        self.cell_text_parts = []
        self.cell_html_parts = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()

        if tag == "tr":
            if self.current_row:
                self._finish_cell()
                self.rows.append(self.current_row)
            self.current_row = []
            return

        if tag in {"th", "td"} and self.current_row is not None:
            # 원문 HTML에 닫는 </td>가 빠진 경우 다음 셀 시작 시 마감한다.
            self._finish_cell()
            attr_dict = {key: value or "" for key, value in attrs}
            self.current_cell = {
                "tag": tag,
                "attrs": " ".join(
                    f'{key}="{value}"'
                    for key, value in attr_dict.items()
                ),
                "html": "",
                "text": "",
            }
            return

        if self.current_cell is not None:
            attrs_text = "".join(
                f' {key}="{value or ""}"'
                for key, value in attrs
            )
            self.cell_html_parts.append(f"<{tag}{attrs_text}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in {"th", "td"}:
            self._finish_cell()
            return

        if tag == "tr":
            self._finish_cell()
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None
            return

        if self.current_cell is not None:
            self.cell_html_parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.cell_text_parts.append(data)
            self.cell_html_parts.append(data)


def _parse_rows(table_html: str) -> list[list[dict[str, Any]]]:
    parser = _TableRowsParser()
    parser.feed(table_html)
    parser._finish_cell()
    if parser.current_row:
        parser.rows.append(parser.current_row)
        parser.current_row = None
    return parser.rows


def _signed_value(cell: dict[str, Any]) -> int | float | None:
    value = _number(cell["text"])
    if value is None:
        return None

    class_text = " ".join(
        re.findall(
            r'class\s*=\s*["\']([^"\']+)["\']',
            cell["html"] + " " + cell["attrs"],
            flags=re.I,
        )
    ).lower()

    numeric = float(value)
    if "down" in class_text and numeric > 0:
        numeric = -numeric
    elif "up" in class_text and numeric < 0:
        numeric = abs(numeric)

    return int(numeric) if numeric.is_integer() else numeric


def _parse_monthly_trend(
    html_text: str,
    *,
    marker: str,
    value_key: str,
) -> dict[str, Any]:
    table_html = _extract_table_after_marker(html_text, marker)
    rows = _parse_rows(table_html)

    if not rows:
        raise ValueError(f"{marker} 표가 비어 있습니다.")

    header = [cell["text"] for cell in rows[0]]
    if len(header) < 3 or header[0] != "지역" or header[1] != "구분":
        raise ValueError(f"{marker} 표 헤더를 인식하지 못했습니다.")

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
            changes = [_signed_value(cell) for cell in row[1:]]
            regions[previous_region]["month_over_month_change_percent"] = changes
            continue

        if len(texts) < 2:
            continue

        region = texts[0]
        values = [_number(cell["text"]) for cell in row[2:]]
        regions[region] = {
            value_key: values,
            "latest_value": values[-1] if values else None,
        }
        previous_region = region

    return {
        "periods": periods,
        "regions": regions,
    }


def _parse_grouped_characteristics(
    html_text: str,
    *,
    marker: str,
    dimensions: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    table_html = _extract_table_after_marker(html_text, marker)
    rows = _parse_rows(table_html)
    dimension_keys = [key for key, _ in dimensions]

    regions: dict[str, dict[str, Any]] = {}
    current_region: str | None = None

    for row in rows:
        texts = [cell["text"] for cell in row]
        if not texts:
            continue

        # 새 지역의 첫 행: [지역, 매출액, ...]
        if len(texts) >= 2 and texts[1] == "매출액":
            current_region = texts[0]
            values = [_number(cell["text"]) for cell in row[2:]]
            regions[current_region] = {
                "amount_10k_krw": dict(zip(dimension_keys, values)),
            }
            continue

        # rowspan 때문에 이어지는 행: [비율, ...] / [매출건수비율, ...]
        if current_region is None:
            continue

        if texts[0] == "비율":
            values = [_number(cell["text"]) for cell in row[1:]]
            regions[current_region]["amount_share_percent"] = dict(
                zip(dimension_keys, values)
            )
        elif texts[0] == "매출건수비율":
            values = [_number(cell["text"]) for cell in row[1:]]
            regions[current_region]["transaction_share_percent"] = dict(
                zip(dimension_keys, values)
            )

    return {
        "dimensions": [
            {"key": key, "label": label}
            for key, label in dimensions
        ],
        "regions": regions,
    }


def _normalize_region_name(name: str) -> str:
    return re.sub(r"\s+", "", name)


def _selected_region(regions: dict[str, Any]) -> dict[str, Any]:
    for name, data in regions.items():
        if _normalize_region_name(name) == "선택영역":
            return data
    return {}


def _year_ago(
    periods: list[str],
    values: list[Any],
) -> tuple[str | None, Any]:
    if not periods or not values or len(periods) != len(values):
        return None, None

    latest = periods[-1]
    match = re.fullmatch(r"(\d{2})\.(\d{2})", latest)
    if not match:
        return None, None

    previous_period = (
        f"{(int(match.group(1)) - 1) % 100:02d}.{match.group(2)}"
    )
    try:
        index = periods.index(previous_period)
    except ValueError:
        return None, None

    return previous_period, values[index]


def _percent_change(current: Any, previous: Any) -> float | None:
    if (
        not isinstance(current, (int, float))
        or not isinstance(previous, (int, float))
        or previous == 0
    ):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 1)


def _signed_reported_percent(value: str, direction: str) -> float:
    number = float(value.replace(",", ""))
    if direction in {
        "적습니다",
        "낮습니다",
        "감소했습니다",
    }:
        return -abs(number)
    return abs(number)


def _extract_analysis_blocks(html_text: str) -> list[str]:
    return re.findall(
        r'<dl\b[^>]*class=["\'][^"\']*\banalyResult\b[^"\']*["\'][^>]*>'
        r'(.*?)</dl>',
        html_text,
        flags=re.I | re.S,
    )


def _extract_reported_analysis(html_text: str) -> dict[str, Any]:
    blocks = _extract_analysis_blocks(html_text)
    texts = [_text(block) for block in blocks]
    combined = " ".join(texts)

    result: dict[str, Any] = {
        "texts": texts,
        "sales_amount_year_over_year_change_percent": None,
        "sales_transactions_year_over_year_change_percent": None,
        "peak_sales_day": None,
        "peak_sales_time_band": None,
        "dominant_sales_gender": None,
        "dominant_sales_age": None,
    }

    amount_match = re.search(
        r"월평균 매출액은 전년동월대비\s*"
        r"([\d,.]+)%\s*"
        r"(많습니다|적습니다|높습니다|낮습니다|증가했습니다|감소했습니다)",
        combined,
    )
    if amount_match:
        result["sales_amount_year_over_year_change_percent"] = (
            _signed_reported_percent(
                amount_match.group(1),
                amount_match.group(2),
            )
        )

    count_match = re.search(
        r"월평균 매출건수는\s*전년동월대비\s*"
        r"([\d,.]+)%\s*"
        r"(많습니다|적습니다|높습니다|낮습니다|증가했습니다|감소했습니다)",
        combined,
    )
    if count_match:
        result["sales_transactions_year_over_year_change_percent"] = (
            _signed_reported_percent(
                count_match.group(1),
                count_match.group(2),
            )
        )

    day_match = re.search(
        r"매출이 가장 많은 요일은\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)",
        combined,
    )
    if day_match:
        result["peak_sales_day"] = DAY_REPORTED_MAP.get(day_match.group(1))

    time_match = re.search(
        r"매출이 가장 많은 시간대는\s*([0-9]{2})[-~]([0-9]{2})시",
        combined,
    )
    if time_match:
        result["peak_sales_time_band"] = (
            f"{time_match.group(1)}_{time_match.group(2)}"
        )

    demographic_match = re.search(
        r"주소비 성,\s*연령대는 각각\s*(남성|여성),\s*"
        r"(10대|20대|30대|40대|50대|60대\s*이상)",
        combined,
    )
    if demographic_match:
        gender_text = demographic_match.group(1)
        age_text = re.sub(r"\s+", " ", demographic_match.group(2)).strip()
        result["dominant_sales_gender"] = GENDER_REPORTED_MAP.get(gender_text)
        result["dominant_sales_age"] = AGE_REPORTED_MAP.get(age_text)

    return result


def _max_key(
    values: dict[str, Any],
    keys: tuple[str, ...] | None = None,
) -> str | None:
    candidates = keys or tuple(values.keys())
    numeric = [
        (key, values.get(key))
        for key in candidates
        if isinstance(values.get(key), (int, float))
    ]
    if not numeric:
        return None
    return max(numeric, key=lambda item: float(item[1]))[0]


def parse_sales_report(html_text: str) -> dict[str, Any]:
    amount_trend = _parse_monthly_trend(
        html_text,
        marker="업소당 월평균 매출액 추이",
        value_key="amount_10k_krw",
    )
    transaction_trend = _parse_monthly_trend(
        html_text,
        marker="업소당 월평균 매출건수 추이",
        value_key="transactions",
    )
    day_characteristics = _parse_grouped_characteristics(
        html_text,
        marker="주중/주말, 요일별 월평균 매출액/매출건수 비율",
        dimensions=DAY_KEYS,
    )
    time_characteristics = _parse_grouped_characteristics(
        html_text,
        marker="시간대별 월평균 매출액/매출건수 비율",
        dimensions=TIME_KEYS,
    )
    demographic_characteristics = _parse_grouped_characteristics(
        html_text,
        marker="성별/연령대별 월평균 매출액/매출건수 비율",
        dimensions=DEMOGRAPHIC_KEYS,
    )
    reported = _extract_reported_analysis(html_text)

    warnings: list[dict[str, Any]] = []

    amount_selected = _selected_region(amount_trend["regions"])
    transaction_selected = _selected_region(transaction_trend["regions"])
    day_selected = _selected_region(day_characteristics["regions"])
    time_selected = _selected_region(time_characteristics["regions"])
    demographic_selected = _selected_region(
        demographic_characteristics["regions"]
    )

    amount_values = amount_selected.get("amount_10k_krw", [])
    transaction_values = transaction_selected.get("transactions", [])

    latest_amount = amount_values[-1] if amount_values else None
    latest_transactions = (
        transaction_values[-1] if transaction_values else None
    )

    amount_year_ago_period, amount_year_ago_value = _year_ago(
        amount_trend["periods"],
        amount_values,
    )
    transaction_year_ago_period, transaction_year_ago_value = _year_ago(
        transaction_trend["periods"],
        transaction_values,
    )

    amount_yoy_computed = _percent_change(
        latest_amount,
        amount_year_ago_value,
    )
    transaction_yoy_computed = _percent_change(
        latest_transactions,
        transaction_year_ago_value,
    )

    amount_yoy_reported = reported[
        "sales_amount_year_over_year_change_percent"
    ]
    transaction_yoy_reported = reported[
        "sales_transactions_year_over_year_change_percent"
    ]

    for code, computed, source_value, label in (
        (
            "sales_amount_yoy_mismatch",
            amount_yoy_computed,
            amount_yoy_reported,
            "매출액",
        ),
        (
            "sales_transactions_yoy_mismatch",
            transaction_yoy_computed,
            transaction_yoy_reported,
            "매출건수",
        ),
    ):
        if (
            computed is not None
            and isinstance(source_value, (int, float))
            and abs(float(computed) - float(source_value)) > 0.2
        ):
            warnings.append(
                {
                    "code": code,
                    "message": (
                        f"{label} 시계열로 계산한 전년동월대비 증감률과 "
                        "분석결과 문구의 값이 다릅니다. 원문 값을 모두 보존했습니다."
                    ),
                    "computed_percent": computed,
                    "reported_percent": source_value,
                }
            )

    day_amount_share = day_selected.get("amount_share_percent", {})
    day_transaction_share = day_selected.get(
        "transaction_share_percent",
        {},
    )
    time_amount_share = time_selected.get("amount_share_percent", {})
    time_transaction_share = time_selected.get(
        "transaction_share_percent",
        {},
    )
    demo_amount_share = demographic_selected.get(
        "amount_share_percent",
        {},
    )
    demo_transaction_share = demographic_selected.get(
        "transaction_share_percent",
        {},
    )

    day_keys_only = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    gender_keys = ("male", "female")
    age_keys = ("teens", "20s", "30s", "40s", "50s", "60_plus")

    peak_sales_day = _max_key(day_amount_share, day_keys_only)
    peak_transaction_day = _max_key(day_transaction_share, day_keys_only)
    peak_sales_time = _max_key(time_amount_share)
    peak_transaction_time = _max_key(time_transaction_share)
    dominant_sales_gender = _max_key(demo_amount_share, gender_keys)
    dominant_transaction_gender = _max_key(
        demo_transaction_share,
        gender_keys,
    )
    dominant_sales_age = _max_key(demo_amount_share, age_keys)
    dominant_transaction_age = _max_key(
        demo_transaction_share,
        age_keys,
    )

    for code, computed, source_value, label in (
        (
            "peak_sales_day_mismatch",
            peak_sales_day,
            reported["peak_sales_day"],
            "최다 매출 요일",
        ),
        (
            "peak_sales_time_mismatch",
            peak_sales_time,
            reported["peak_sales_time_band"],
            "최다 매출 시간대",
        ),
        (
            "dominant_sales_gender_mismatch",
            dominant_sales_gender,
            reported["dominant_sales_gender"],
            "주소비 성별",
        ),
        (
            "dominant_sales_age_mismatch",
            dominant_sales_age,
            reported["dominant_sales_age"],
            "주소비 연령대",
        ),
    ):
        if source_value is not None and computed != source_value:
            warnings.append(
                {
                    "code": code,
                    "message": (
                        f"표에서 계산한 {label}과 분석결과 문구가 다릅니다. "
                        "원문 값을 모두 보존했습니다."
                    ),
                    "computed": computed,
                    "reported": source_value,
                }
            )

    return {
        "schema_version": "sbiz365.sales.v0.1",
        "source": {
            "report": "sang_gwon3.sg",
            "note": (
                "HTML tables and analysis-result text normalized "
                "without executing JavaScript"
            ),
            "amount_unit": "10k_krw",
        },
        "monthly_average_sales_amount": amount_trend,
        "monthly_average_sales_transactions": transaction_trend,
        "sales_characteristics": {
            "day_of_week": day_characteristics,
            "time_band": time_characteristics,
            "demographics": demographic_characteristics,
        },
        "reported_analysis": reported,
        "derived_selected_area": {
            "latest_period": (
                amount_trend["periods"][-1]
                if amount_trend["periods"]
                else None
            ),
            "latest_monthly_average_sales_amount_10k_krw": latest_amount,
            "sales_amount_year_ago_period": amount_year_ago_period,
            "sales_amount_year_ago_10k_krw": amount_year_ago_value,
            "sales_amount_year_over_year_change_percent_computed": (
                amount_yoy_computed
            ),
            "sales_amount_year_over_year_change_percent_reported": (
                amount_yoy_reported
            ),
            "latest_monthly_average_sales_transactions": latest_transactions,
            "sales_transactions_year_ago_period": (
                transaction_year_ago_period
            ),
            "sales_transactions_year_ago": transaction_year_ago_value,
            "sales_transactions_year_over_year_change_percent_computed": (
                transaction_yoy_computed
            ),
            "sales_transactions_year_over_year_change_percent_reported": (
                transaction_yoy_reported
            ),
            "peak_sales_day": peak_sales_day,
            "peak_transaction_day": peak_transaction_day,
            "peak_sales_time_band": peak_sales_time,
            "peak_transaction_time_band": peak_transaction_time,
            "dominant_sales_gender": dominant_sales_gender,
            "dominant_transaction_gender": dominant_transaction_gender,
            "dominant_sales_age": dominant_sales_age,
            "dominant_transaction_age": dominant_transaction_age,
        },
        "warnings": warnings,
    }


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "사용법: python quant_sales.py <sang_gwon3.raw.html> [output.json]",
            file=sys.stderr,
        )
        return 1

    input_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else input_path.with_suffix(".normalized.json")
    )

    html_text = input_path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    result = parse_sales_report(html_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    derived = result["derived_selected_area"]

    print("매출분석 파싱 성공")
    print(
        "최신 업소당 월평균 매출액: "
        f"{derived['latest_monthly_average_sales_amount_10k_krw']}만원"
    )
    print(
        "매출액 전년동월대비: "
        f"{derived['sales_amount_year_over_year_change_percent_reported']}%"
    )
    print(
        "최신 업소당 월평균 매출건수: "
        f"{derived['latest_monthly_average_sales_transactions']}건"
    )
    print(
        "매출건수 전년동월대비: "
        f"{derived['sales_transactions_year_over_year_change_percent_reported']}%"
    )
    print(f"최다 매출 요일: {derived['peak_sales_day']}")
    print(f"최다 매출 시간대: {derived['peak_sales_time_band']}")
    print(
        "주소비 성별/연령대: "
        f"{derived['dominant_sales_gender']} / "
        f"{derived['dominant_sales_age']}"
    )

    if result["warnings"]:
        print()
        print("경고:")
        for warning in result["warnings"]:
            print(f"- {warning['code']}: {warning['message']}")

    print()
    print(f"저장 위치: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
