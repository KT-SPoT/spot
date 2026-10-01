"""SBIZ365 상세분석 수집 헬퍼.

브라우저에서 검증한 상세분석 흐름을 함수 형태로 제공한다.
인증키는 인자로만 받고 파일/로그에 저장하지 않는다.
"""

from __future__ import annotations

import json
import math
import re
from html import unescape
from http.cookiejar import CookieJar
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from pyproj import Transformer


BASE_URL = "https://bigdata.sbiz.or.kr"
DETAIL_PATH = "/gis/openApi/detail"
CAPTURE_PATH = "/gis/com/report/capture.json"

DEFAULT_UPJONG_CD = "G20802"

GEO_TO_5181 = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:5181",
    always_xy=True,
)


class Sbiz365Error(RuntimeError):
    """SBIZ365 수집 과정에서 발생한 오류."""


def _make_opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def _read_text(response) -> str:
    return response.read().decode("utf-8", errors="replace")


def _extract_js_var(html: str, var_name: str) -> str | None:
    pattern = rf'\bvar\s+{re.escape(var_name)}\s*=\s*"([^"]*)"'
    match = re.search(pattern, html)
    if not match:
        return None
    return unescape(match.group(1)).strip()


def _request_text(
    opener,
    url: str,
    headers: dict[str, str],
    *,
    method: str = "GET",
    data: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    request = Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    with opener.open(request, timeout=timeout) as response:
        return (
            response.status,
            response.headers.get("Content-Type", ""),
            _read_text(response),
        )


def collect_sbiz365_reports(
    *,
    lat: float,
    lng: float,
    radius_m: int,
    cert_key: str,
    upjong_cd: str = DEFAULT_UPJONG_CD,
    report_numbers: Iterable[int] = (4,),
) -> dict[str, Any]:
    """수집한 상세분석 리포트 HTML과 메타데이터를 반환한다.

    현재 검증된 report 번호:
    2=업종분석, 3=매출분석, 4=인구분석,
    6=지역현황, 7=고객특성, 8=추가영역.
    """

    if not cert_key.strip():
        raise Sbiz365Error("SBIZ365_CERT_KEY가 비어 있습니다.")

    if radius_m <= 0:
        raise Sbiz365Error("radius_m은 1 이상의 정수여야 합니다.")

    allowed_reports = {2, 3, 4, 6, 7, 8}
    requested_reports = tuple(dict.fromkeys(int(n) for n in report_numbers))

    invalid_reports = [
        report_no
        for report_no in requested_reports
        if report_no not in allowed_reports
    ]
    if invalid_reports:
        raise Sbiz365Error(
            f"지원하지 않는 report 번호입니다: {invalid_reports}"
        )

    transform_x_float, transform_y_float = GEO_TO_5181.transform(lng, lat)
    transform_x = math.floor(transform_x_float)
    transform_y = math.floor(transform_y_float)

    opener = _make_opener()

    common_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    detail_query = urlencode(
        {
            "certKey": cert_key,
            "type": "detail",
            "rptpType": "gisDetail",
        }
    )
    detail_url = f"{BASE_URL}{DETAIL_PATH}?{detail_query}"

    try:
        _request_text(
            opener,
            detail_url,
            common_headers,
        )
    except (HTTPError, URLError) as exc:
        raise Sbiz365Error(f"상세분석 페이지 진입 실패: {exc}") from exc

    capture_payload = {
        "type": "circleRadius",
        "analyType": "bizonAnls",
        "centerX": lat,
        "centerY": lng,
        "transformX": transform_x,
        "transformY": transform_y,
        "upjongCd": upjong_cd,
        "kakaoPathStr": "",
        "pathStr": "",
        "radius": radius_m,
        "mapLevelDecision": radius_m,
        "apiLogin": "N",
        "sprNo": 0,
    }

    capture_headers = {
        **common_headers,
        "Accept": "*/*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": BASE_URL,
        "Referer": detail_url,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        _, _, capture_text = _request_text(
            opener,
            f"{BASE_URL}{CAPTURE_PATH}",
            capture_headers,
            method="POST",
            data=json.dumps(
                capture_payload,
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        capture_data = json.loads(capture_text)
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise Sbiz365Error(
            f"capture.json HTTP {exc.code}: {body[:500]}"
        ) from exc
    except (URLError, json.JSONDecodeError) as exc:
        raise Sbiz365Error(f"capture.json 요청 실패: {exc}") from exc

    analy_no = capture_data.get("analyNo")
    analy_date = capture_data.get("analyDate")
    km_analy_no = capture_data.get("kmAnalyNo", "")

    if not analy_no or not analy_date:
        raise Sbiz365Error(
            "capture.json 응답에 analyNo/analyDate가 없습니다."
        )

    report_headers = {
        **common_headers,
        "Accept": "*/*",
        "Referer": detail_url,
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    sg1_params = {
        "analyNo": analy_no,
        "upjongCd": upjong_cd,
        "xcnts": transform_x,
        "ydnts": transform_y,
        "center_x": transform_x,
        "center_y": transform_y,
        "analyDate": analy_date,
        "a": "01",
        "b": "01",
        "c": "01",
        "apiLogin": "",
        "lKey": "",
        "xtLoginId": cert_key,
    }

    sg1_url = (
        f"{BASE_URL}/gis/bizonAnls/report/sg/sang_gwon1.sg?"
        + urlencode(sg1_params)
    )

    try:
        _, _, sg1_html = _request_text(
            opener,
            sg1_url,
            report_headers,
        )
    except (HTTPError, URLError) as exc:
        raise Sbiz365Error(f"sang_gwon1.sg 요청 실패: {exc}") from exc

    admi_cd = _extract_js_var(sg1_html, "aACd")
    admi_nm = _extract_js_var(sg1_html, "aANm")

    if not admi_cd or not admi_nm:
        raise Sbiz365Error(
            "sang_gwon1.sg에서 행정동 정보(aACd/aANm)를 찾지 못했습니다."
        )

    param_data = {
        "analyNo": analy_no,
        "analyDate": analy_date,
        "upjongCd": upjong_cd,
        "admiCd": admi_cd,
        "admiNm": admi_nm,
        "kmAnalyNo": km_analy_no or "",
        "xtLoginId": cert_key,
    }

    reports: dict[int, dict[str, Any]] = {}

    for report_no in requested_reports:
        report_name = f"sang_gwon{report_no}.sg"
        report_url = (
            f"{BASE_URL}/gis/bizonAnls/report/sg/{report_name}?"
            + urlencode(param_data)
        )

        try:
            status, content_type, html = _request_text(
                opener,
                report_url,
                report_headers,
            )
        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            raise Sbiz365Error(
                f"{report_name} HTTP {exc.code}: {body[:500]}"
            ) from exc
        except URLError as exc:
            raise Sbiz365Error(
                f"{report_name} 네트워크 오류: {exc.reason}"
            ) from exc

        reports[report_no] = {
            "report": report_name,
            "status": status,
            "content_type": content_type,
            "html": html,
        }

    return {
        "analy_no": analy_no,
        "analy_date": analy_date,
        "admi_cd": admi_cd,
        "admi_nm": admi_nm,
        "km_analy_no_present": km_analy_no not in (None, ""),
        "analysis": {
            "lat": lat,
            "lng": lng,
            "transform_x": transform_x,
            "transform_y": transform_y,
            "radius_m": radius_m,
            "upjong_cd": upjong_cd,
        },
        "reports": reports,
    }
