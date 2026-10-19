from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoGeocodeError(RuntimeError):
    pass


def _request_json(
    url: str,
    *,
    params: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)

    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "Authorization": f"KakaoAK {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""

        raise KakaoGeocodeError(
            f"KAKAO_HTTP_ERROR: HTTP {exc.code} {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise KakaoGeocodeError(
            f"KAKAO_NETWORK_ERROR: {exc.reason}"
        ) from exc


def resolve_address(
    address: str,
    *,
    api_key: str,
) -> dict[str, Any]:
    address = (address or "").strip()
    api_key = (api_key or "").strip()

    if not address:
        raise KakaoGeocodeError("EMPTY_ADDRESS")

    if not api_key:
        raise KakaoGeocodeError("MISSING_KAKAO_REST_API_KEY")

    # 1. 정확한 도로명/지번 주소 검색
    address_data = _request_json(
        KAKAO_ADDRESS_URL,
        params={
            "query": address,
            "page": 1,
            "size": 10,
        },
        api_key=api_key,
    )

    address_docs = address_data.get("documents") or []

    if address_docs:
        item = address_docs[0]

        return {
            "input_address": address,
            "resolved_name": item.get("address_name") or address,
            "lat": float(item["y"]),
            "lng": float(item["x"]),
            "coordinate_source": "kakao_address",
        }

    # 2. 행정동처럼 일반 주소 검색으로 잡히지 않으면
    #    행정복지센터를 해당 행정동의 대표 지점으로 사용
    keyword_data = _request_json(
        KAKAO_KEYWORD_URL,
        params={
            "query": f"{address} 행정복지센터",
            "page": 1,
            "size": 15,
        },
        api_key=api_key,
    )

    keyword_docs = keyword_data.get("documents") or []

    preferred = [
        item
        for item in keyword_docs
        if "행정복지센터" in (item.get("place_name") or "")
        and "무인민원" not in (item.get("place_name") or "")
        and "충전소" not in (item.get("place_name") or "")
    ]

    if preferred:
        item = preferred[0]

        return {
            "input_address": address,
            "resolved_name": item.get("place_name") or address,
            "resolved_address": (
                item.get("road_address_name")
                or item.get("address_name")
            ),
            "lat": float(item["y"]),
            "lng": float(item["x"]),
            "coordinate_source": "kakao_administrative_center",
        }

    raise KakaoGeocodeError(
        f"ADDRESS_NOT_FOUND: {address}"
    )
