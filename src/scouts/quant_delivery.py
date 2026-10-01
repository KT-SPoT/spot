"""SBIZ365 배달매출/추가영역(sang_gwon8.sg) parser.

현재 확인된 응답은 비어 있는 탭 컨테이너만 반환한다.
데이터가 없는 경우 실패하지 않고 unavailable 상태로 정규화한다.
"""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_text(html_text: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_text)
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()


def parse_delivery_report(html_text: str) -> dict[str, Any]:
    visible = _visible_text(html_text)

    # 현재 샘플에서는 빈 컨테이너(<div class="bizonTab7"></div>)만 존재한다.
    has_tab_container = bool(
        re.search(
            r'<div\b[^>]*class=["\'][^"\']*\bbizonTab7\b[^"\']*["\'][^>]*>',
            html_text,
            flags=re.I,
        )
    )

    # 주석 텍스트는 데이터로 취급하지 않는다.
    without_comments = re.sub(
        r"<!--.*?-->",
        "",
        html_text,
        flags=re.S,
    )
    without_empty_container = re.sub(
        r'<div\b[^>]*class=["\'][^"\']*\bbizonTab7\b[^"\']*["\'][^>]*>\s*</div>',
        "",
        without_comments,
        flags=re.I | re.S,
    )
    meaningful_html = without_empty_container.strip()
    has_delivery_sales_data = bool(
        visible or meaningful_html
    )

    warnings: list[dict[str, Any]] = []

    if not has_delivery_sales_data:
        warnings.append(
            {
                "code": "delivery_sales_data_unavailable",
                "message": (
                    "이 상세분석 응답에는 배달매출 데이터가 제공되지 않았습니다. "
                    "빈 값을 임의로 추정하지 않고 그대로 보존합니다."
                ),
            }
        )
    else:
        warnings.append(
            {
                "code": "delivery_sales_payload_unparsed",
                "message": (
                    "배달매출 응답에 내용이 존재하지만 현재 파서에서 구조를 "
                    "검증하지 못했습니다. 실제 데이터가 있는 샘플로 파서 확장이 필요합니다."
                ),
            }
        )

    return {
        "schema_version": "sbiz365.delivery.v0.1",
        "source": {
            "report": "sang_gwon8.sg",
            "note": (
                "현재 확인된 응답은 배달매출 탭 컨테이너만 포함합니다."
            ),
        },
        "delivery_sales": {
            "available": has_delivery_sales_data,
            "tab_container_present": has_tab_container,
            "visible_text": visible or None,
        },
        "derived_selected_area": {
            "has_delivery_sales_data": has_delivery_sales_data,
        },
        "warnings": warnings,
    }


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "사용법: python quant_delivery.py "
            "<sang_gwon8.raw.html> [output.json]",
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
    result = parse_delivery_report(html_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    derived = result["derived_selected_area"]

    print("배달매출 파싱 성공")
    print(
        "배달매출 데이터 존재: "
        f"{derived['has_delivery_sales_data']}"
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
