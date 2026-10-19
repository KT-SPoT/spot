"""Safe, actionable failure summaries using existing Brief manual-check text."""
import re


def failure_summary(module, errors):
    fallback = "조사 중 오류가 발생해 자료를 확보하지 못했습니다."
    if module != "quant":
        return fallback
    for error in errors:
        if not isinstance(error, dict):
            continue
        code = error.get("code")
        messages = {
            "MISSING_SBIZ365_CERT_KEY": "소상공인365 인증키가 서버에 설정되지 않았습니다.",
            "MISSING_KAKAO_REST_API_KEY": "주소 조회용 카카오 키가 서버에 설정되지 않았습니다.",
            "ADDRESS_GEOCODING_ERROR": "매장 주소를 좌표로 변환하지 못했습니다. 지도에서 위치를 다시 선택해주세요.",
            "MISSING_LOCATION": "매장 위치가 없습니다. 지도에서 위치를 선택해주세요.",
            "INVALID_RADIUS": "조사 반경을 확인해주세요.",
            "SBIZ365_CORE_REPORTS_UNAVAILABLE": "소상공인365 응답에서 핵심 상권 자료를 읽지 못했습니다.",
        }
        if code in messages:
            return messages[code]
        if code == "SBIZ365_COLLECTION_ERROR":
            # Recognize only HTTP status digits; never relay raw URLs/body/key text.
            match = re.search(r"\bHTTP(?: Error)? (\d{3})\b", str(error.get("message", "")))
            status = int(match[1]) if match else None
            if status in (500, 502, 503, 504):
                return (f"소상공인365 서버가 일시적으로 응답하지 않습니다(HTTP {status}). "
                        "잠시 후 새 조사를 시작해주세요. 현재 브리프는 보존됩니다.")
            if status in (401, 403):
                return f"소상공인365 인증 또는 이용 권한을 확인해야 합니다(HTTP {status})."
            if status == 429:
                return "소상공인365 호출 제한에 도달했습니다. 잠시 후 다시 조사해주세요."
            return "소상공인365 상세분석 연결에 실패했습니다. 서비스 상태와 서버 연결을 확인해주세요."
    return fallback
