import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class TableParser(HTMLParser):
    """Very small stdlib-only HTML table extractor."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table_depth = 0
        self.current_table = None
        self.in_row = False
        self.in_cell = False
        self.in_caption = False
        self.row = []
        self.cell_parts = []
        self.caption_parts = []

    @staticmethod
    def clean_text(value):
        return " ".join(value.split())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "table":
            self.table_depth += 1
            if self.table_depth == 1:
                self.current_table = {"caption": "", "rows": []}

        elif self.table_depth == 1 and tag == "tr":
            self.in_row = True
            self.row = []

        elif self.table_depth == 1 and tag in ("th", "td") and self.in_row:
            self.in_cell = True
            self.cell_parts = []

        elif self.table_depth == 1 and tag == "caption":
            self.in_caption = True
            self.caption_parts = []

    def handle_data(self, data):
        if self.in_cell:
            self.cell_parts.append(data)

        if self.in_caption:
            self.caption_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "table":
            if self.table_depth == 1 and self.current_table is not None:
                self.tables.append(self.current_table)
                self.current_table = None
            self.table_depth -= 1

        elif self.table_depth == 1 and tag in ("th", "td") and self.in_cell:
            text = self.clean_text("".join(self.cell_parts))
            self.row.append(text)
            self.in_cell = False

        elif self.table_depth == 1 and tag == "tr" and self.in_row:
            if self.row:
                self.current_table["rows"].append(self.row)
            self.in_row = False

        elif self.table_depth == 1 and tag == "caption" and self.in_caption:
            self.current_table["caption"] = self.clean_text(
                "".join(self.caption_parts)
            )
            self.in_caption = False


def num(text):
    text = str(text).strip().replace(",", "").replace("%", "")
    if text in ("", "-"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return float(text)
    return text


def value_range(text):
    match = re.fullmatch(
        r"\s*([\d,]+(?:\.\d+)?)\s*~\s*([\d,]+(?:\.\d+)?)\s*",
        str(text),
    )
    if not match:
        return text
    return {"min": num(match.group(1)), "max": num(match.group(2))}


def find_table(tables, *, caption_contains=None, row_contains=None):
    for table in tables:
        if caption_contains and caption_contains not in table["caption"]:
            continue
        if row_contains:
            joined = " | ".join(" | ".join(row) for row in table["rows"][:3])
            if not all(term in joined for term in row_contains):
                continue
        return table
    raise ValueError(
        f"table not found: caption_contains={caption_contains!r}, "
        f"row_contains={row_contains!r}"
    )


def paired_region_rows(table, labels, share_labels=None):
    """
    Parses tables shaped like:
      [region, '인구', values...]
      ['비율', values...]

    share_labels lets a table omit a percentage for one or more count columns.
    Example: 유동인구 성별/연령 표 has daily_total count, but no daily_total share.
    """
    result = {}
    rows = table["rows"]
    share_labels = share_labels or labels
    i = 0

    while i < len(rows):
        row = rows[i]

        if len(row) >= 3 and row[1] == "인구":
            region = row[0]
            counts = [num(x) for x in row[2:]]
            entry = {
                label: counts[idx] if idx < len(counts) else None
                for idx, label in enumerate(labels)
            }

            if i + 1 < len(rows) and rows[i + 1] and rows[i + 1][0] == "비율":
                shares = [num(x) for x in rows[i + 1][1:]]
                for idx, label in enumerate(share_labels):
                    if idx < len(shares) and label in entry:
                        current = entry[label]
                        entry[label] = {
                            "count": current,
                            "share_pct": shares[idx],
                        }
                i += 1

            result[region] = entry

        i += 1

    return result


def trend_table(table):
    rows = table["rows"]
    periods = rows[0][1:]
    regions = {}

    for row in rows[1:]:
        if len(row) >= 2:
            regions[row[0]] = [num(x) for x in row[1:]]

    return {
        "periods": periods,
        "regions": regions,
    }


def income_consumption_trend(table):
    rows = table["rows"]
    periods = rows[1]
    regions = {}

    for row in rows[2:]:
        if len(row) < 5:
            continue

        regions[row[0]] = {
            "income": {
                periods[0]: value_range(row[1]),
                periods[1]: value_range(row[2]),
            },
            "consumption": {
                periods[2]: value_range(row[3]),
                periods[3]: value_range(row[4]),
            },
        }

    return {
        "unit": "만원",
        "regions": regions,
    }


def income_consumption_demographic(table, dimension):
    rows = table["rows"]
    periods = rows[1]
    groups = {}

    for row in rows[2:]:
        if len(row) < 5:
            continue

        groups[row[0]] = {
            "income": {
                periods[0]: value_range(row[1]),
                periods[1]: value_range(row[2]),
            },
            "consumption": {
                periods[2]: value_range(row[3]),
                periods[3]: value_range(row[4]),
            },
        }

    return {
        "unit": "만원",
        "dimension": dimension,
        "groups": groups,
    }


def parse_population_report(html_text):
    parser = TableParser()
    parser.feed(html_text)
    tables = parser.tables

    # ---- 유동인구 월별 추이 ----
    monthly = None
    for candidate in tables:
        rows = candidate["rows"]
        if not rows:
            continue
        header = rows[0]
        if (
            len(header) >= 4
            and header[:2] == ["지역", "구분"]
            and all(re.fullmatch(r"\d{2}\.\d{2}", cell) for cell in header[2:])
        ):
            monthly = candidate
            break

    if monthly is None:
        raise ValueError("월별 일평균 유동인구 표를 찾지 못했습니다.")
    monthly_rows = monthly["rows"]
    monthly_periods = monthly_rows[0][2:]
    monthly_regions = {}

    i = 1
    while i < len(monthly_rows):
        row = monthly_rows[i]
        if len(row) >= 3 and row[1] == "인구":
            region = row[0]
            monthly_regions[region] = [num(x) for x in row[2:]]
        i += 1

    # ---- 유동인구 성별/연령 ----
    flow_demo_table = find_table(
        tables,
        row_contains=["일일", "남성", "여성", "60대이상"],
    )
    flow_labels = [
        "daily_total",
        "male",
        "female",
        "teens",
        "20s",
        "30s",
        "40s",
        "50s",
        "60_plus",
    ]
    flow_demo = paired_region_rows(
        flow_demo_table,
        flow_labels,
        share_labels=flow_labels[1:],
    )

    # ---- 유동인구 주중/주말 + 요일 ----
    weekday_table = find_table(
        tables,
        row_contains=["주중", "주말", "월", "화", "금", "토", "일"],
    )
    weekday_labels = [
        "weekday",
        "weekend",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    ]
    weekday_data = paired_region_rows(weekday_table, weekday_labels)

    # ---- 유동인구 시간대 ----
    time_table = find_table(
        tables,
        row_contains=["05~09시", "09~12시", "18~23시", "23~05시"],
    )
    time_labels = [
        "05_09",
        "09_12",
        "12_14",
        "14_18",
        "18_23",
        "23_05",
    ]
    time_data = paired_region_rows(time_table, time_labels)

    # ---- 주거인구 ----
    resident_trend_table = find_table(
        tables,
        caption_contains="주거인구 추이",
    )
    resident_trend = trend_table(resident_trend_table)

    resident_demo_table = find_table(
        tables,
        caption_contains="성별/연령대별 주거인구",
    )
    resident_labels = [
        "total",
        "male",
        "female",
        "under_10",
        "teens",
        "20s",
        "30s",
        "40s",
        "50s",
        "60_plus",
    ]
    resident_demo = paired_region_rows(resident_demo_table, resident_labels)

    resident_ic_trend = income_consumption_trend(
        find_table(tables, caption_contains="주거인구 소득소비 추이")
    )
    resident_ic_gender = income_consumption_demographic(
        find_table(
            tables,
            caption_contains="인구분석 - 성별 소득소비",
        ),
        "gender",
    )
    resident_ic_age = income_consumption_demographic(
        find_table(
            tables,
            caption_contains="인구분석 - 연령대별 소득소비",
        ),
        "age",
    )

    # ---- 직장인구 ----
    worker_trend = trend_table(
        find_table(tables, caption_contains="직장인구 추이")
    )

    worker_demo_table = find_table(
        tables,
        caption_contains="성별/연령대별 직장인구",
    )
    worker_labels = [
        "total",
        "male",
        "female",
        "20s",
        "30s",
        "40s",
        "50s",
        "60_plus",
    ]
    worker_demo = paired_region_rows(worker_demo_table, worker_labels)

    worker_ic_trend = income_consumption_trend(
        find_table(tables, caption_contains="직장인구 소득소비 추이")
    )
    worker_ic_gender = income_consumption_demographic(
        find_table(
            tables,
            caption_contains="직장인구 - 성별 소득소비",
        ),
        "gender",
    )
    worker_ic_age = income_consumption_demographic(
        find_table(
            tables,
            caption_contains="직장인구 - 연령대별 소득소비",
        ),
        "age",
    )

    selected_flow_demo = flow_demo.get("선택 영역", {})
    selected_weekday = weekday_data.get("선택 영역", {})
    selected_time = time_data.get("선택 영역", {})
    selected_resident_demo = resident_demo.get("선택 영역", {})
    selected_worker_demo = worker_demo.get("선택 영역", {})

    def max_share_key(mapping, keys):
        candidates = []
        for key in keys:
            value = mapping.get(key)
            if isinstance(value, dict) and isinstance(value.get("share_pct"), (int, float)):
                candidates.append((value["share_pct"], key))
        return max(candidates)[1] if candidates else None

    peak_day = max_share_key(
        selected_weekday,
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    )
    peak_time = max_share_key(
        selected_time,
        ["05_09", "09_12", "12_14", "14_18", "18_23", "23_05"],
    )

    resident_selected = resident_trend["regions"].get("선택 영역", [])
    worker_selected = worker_trend["regions"].get("선택 영역", [])
    monthly_selected = monthly_regions.get("선택 영역", [])

    output = {
        "schema_version": "sbiz365.population.v0.1",
        "source": {
            "report": "sang_gwon4.sg",
            "note": "HTML response normalized without executing JavaScript",
        },
        "floating_population": {
            "monthly_daily_average": {
                "unit": "persons",
                "periods": monthly_periods,
                "regions": monthly_regions,
            },
            "demographics": {
                "unit": "persons",
                "regions": flow_demo,
            },
            "weekday_weekend_and_day_of_week": {
                "unit": "persons",
                "regions": weekday_data,
            },
            "time_band": {
                "unit": "persons",
                "regions": time_data,
            },
        },
        "resident_population": {
            "trend": {
                "unit": "persons",
                **resident_trend,
            },
            "demographics": {
                "unit": "persons",
                "regions": resident_demo,
            },
            "income_consumption_trend": resident_ic_trend,
            "income_consumption_by_gender": resident_ic_gender,
            "income_consumption_by_age": resident_ic_age,
        },
        "worker_population": {
            "trend": {
                "unit": "persons",
                **worker_trend,
            },
            "demographics": {
                "unit": "persons",
                "regions": worker_demo,
            },
            "income_consumption_trend": worker_ic_trend,
            "income_consumption_by_gender": worker_ic_gender,
            "income_consumption_by_age": worker_ic_age,
        },
        "derived_selected_area": {
            "latest_monthly_daily_flow_population": (
                monthly_selected[-1] if monthly_selected else None
            ),
            "dominant_flow_gender": max_share_key(
                selected_flow_demo, ["male", "female"]
            ),
            "dominant_flow_age": max_share_key(
                selected_flow_demo,
                ["teens", "20s", "30s", "40s", "50s", "60_plus"],
            ),
            "peak_day_of_week": peak_day,
            "peak_time_band": peak_time,
            "latest_resident_population_from_trend": (
                resident_selected[-1] if resident_selected else None
            ),
            "resident_population_demographic_total": (
                selected_resident_demo.get("total", {}).get("count")
                if isinstance(selected_resident_demo.get("total"), dict)
                else selected_resident_demo.get("total")
            ),
            "latest_worker_population_from_trend": (
                worker_selected[-1] if worker_selected else None
            ),
            "worker_population_demographic_total": (
                selected_worker_demo.get("total", {}).get("count")
                if isinstance(selected_worker_demo.get("total"), dict)
                else selected_worker_demo.get("total")
            ),
        },
        "warnings": [],
    }

    # 원문 자체의 표 간 값 불일치는 임의로 고치지 않고 경고만 남긴다.
    trend_resident = output["derived_selected_area"][
        "latest_resident_population_from_trend"
    ]
    demo_resident = output["derived_selected_area"][
        "resident_population_demographic_total"
    ]

    if (
        isinstance(trend_resident, (int, float))
        and isinstance(demo_resident, (int, float))
        and trend_resident != demo_resident
    ):
        output["warnings"].append(
            {
                "code": "resident_population_source_mismatch",
                "message": (
                    "주거인구 추이의 최신 선택영역 값과 "
                    "성별/연령대별 주거인구의 전체 값이 서로 다릅니다. "
                    "원문 값을 그대로 보존했습니다."
                ),
                "trend_latest": trend_resident,
                "demographic_total": demo_resident,
            }
        )

    return output


def main():
    if len(sys.argv) < 2:
        print(
            "사용법: python parse_sbiz365_population.py "
            "<sang_gwon4.raw.html> [output.json]"
        )
        return 1

    input_path = Path(sys.argv[1])

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name("sang_gwon4.normalized.json")

    html_text = input_path.read_text(encoding="utf-8", errors="replace")
    data = parse_population_report(html_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    d = data["derived_selected_area"]

    print("인구분석 파싱 성공")
    print(f"월별 최신 일평균 유동인구: {d['latest_monthly_daily_flow_population']}")
    print(f"유동인구 우세 성별: {d['dominant_flow_gender']}")
    print(f"유동인구 우세 연령대: {d['dominant_flow_age']}")
    print(f"최다 요일: {d['peak_day_of_week']}")
    print(f"최다 시간대: {d['peak_time_band']}")
    print(f"주거인구 최신값: {d['latest_resident_population_from_trend']}")
    print(f"직장인구 최신값: {d['latest_worker_population_from_trend']}")

    if data["warnings"]:
        print()
        print("경고:")
        for warning in data["warnings"]:
            print(f"- {warning['code']}: {warning['message']}")

    print()
    print(f"저장 위치: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
