"""Bounded provider searches. Provider errors never include URLs or credentials."""
import html
import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

KST = timezone(timedelta(hours=9))


class SearchError(Exception):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


def window(request):
    research = request.get("research") or {}
    raw = research.get("reference_date") or request.get("requested_at") or now()
    end = date.fromisoformat(raw[:10])
    days = research.get("lookback_days", 180)
    if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days <= 3650:
        raise ValueError("Invalid lookback_days")
    return end - timedelta(days=days), end, days


def clean(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip()


def normalized(value):
    return re.sub(r"[^a-z0-9가-힣]", "", clean(value).lower())


def credentials():
    if os.getenv("SPOT_SCOUT_MODE") == "offline":
        raise SearchError("OFFLINE_MODE")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", encoding="utf-8-sig")


def get_json(endpoint, params, headers=None):
    try:
        # No raw exceptions, response bodies, request objects or secret URLs escape.
        with urlopen(Request(endpoint + "?" + urlencode(params), headers=headers or {}), timeout=15) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise SearchError("RESPONSE_TOO_LARGE")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise SearchError("INVALID_PROVIDER_RESPONSE")
        return result
    except HTTPError as exc:
        raise SearchError("PROVIDER_HTTP_ERROR", exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise SearchError("PROVIDER_UNAVAILABLE") from None
    except (ValueError, UnicodeError):
        raise SearchError("INVALID_PROVIDER_RESPONSE") from None


def news(query, start, end):
    credentials()
    client = os.getenv("NAVER_CLIENT_ID", "")
    secret = os.getenv("NAVER_CLIENT_SECRET", "")
    if not client or not secret:
        raise SearchError("MISSING_NAVER_CREDENTIALS")
    provider = os.getenv("NAVER_SEARCH_PROVIDER", "auto")
    if provider not in ("auto", "legacy", "hub"):
        raise SearchError("INVALID_NAVER_PROVIDER")
    endpoints = [("https://openapi.naver.com/v1/search/news.json",
                  {"X-Naver-Client-Id": client, "X-Naver-Client-Secret": secret}),
                 ("https://naverapihub.apigw.ntruss.com/search/v1/news",
                  {"X-NCP-APIGW-API-KEY-ID": client, "X-NCP-APIGW-API-KEY": secret})]
    selected = 1 if provider == "hub" else 0
    items = []
    for offset in (1, 101):
        params = {"query": query, "display": 100, "start": offset, "sort": "date"}
        try:
            data = get_json(endpoints[selected][0], params, endpoints[selected][1])
        except SearchError as exc:
            if provider != "auto" or selected != 0 or exc.status not in (401, 403):
                raise
            selected = 1
            data = get_json(endpoints[1][0], params, endpoints[1][1])
        batch = data.get("items")
        if not isinstance(batch, list):
            raise SearchError("INVALID_PROVIDER_RESPONSE")
        for item in batch:
            if not isinstance(item, dict):
                continue
            try:
                published = parsedate_to_datetime(item.get("pubDate", ""))
                if published.tzinfo is None:
                    continue
                published = published.astimezone(KST)
            except (ValueError, TypeError, AttributeError):
                continue
            url = item.get("originallink") or item.get("link")
            if start <= published.date() <= end and isinstance(url, str) and urlsplit(url).scheme in ("http", "https"):
                items.append({"title": clean(item.get("title")), "description": clean(item.get("description")),
                              "source_url": url, "published_at": published.isoformat(),
                              "source_name": urlsplit(url).hostname, "source_type": "news",
                              "date_basis": "naver_provided_at", "collected_at": now()})
        if len(batch) < 100:
            break
    return items


def videos(query, start, end):
    credentials()
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        raise SearchError("MISSING_YOUTUBE_API_KEY")
    def utc(day):
        return datetime.combine(day, time.min, KST).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    data = get_json("https://www.googleapis.com/youtube/v3/search", {
        "key": key, "part": "snippet", "type": "video", "q": query, "maxResults": 25,
        "order": "date", "relevanceLanguage": "ko", "regionCode": "KR",
        "publishedAfter": utc(start), "publishedBefore": utc(end + timedelta(days=1))})
    batch = data.get("items")
    if not isinstance(batch, list):
        raise SearchError("INVALID_PROVIDER_RESPONSE")
    ids = [i["id"].get("videoId") for i in batch
           if isinstance(i, dict) and isinstance(i.get("id"), dict)]
    ids = [i for i in ids if isinstance(i, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", i)]
    if not ids:
        return []
    details = get_json("https://www.googleapis.com/youtube/v3/videos", {
        "key": key, "part": "snippet", "id": ",".join(ids)})
    items = []
    batch = details.get("items")
    if not isinstance(batch, list):
        raise SearchError("INVALID_PROVIDER_RESPONSE")
    for item in batch:
        if not isinstance(item, dict) or not isinstance(item.get("snippet"), dict):
            continue
        snippet = item.get("snippet", {})
        try:
            published = datetime.fromisoformat(snippet.get("publishedAt", "").replace("Z", "+00:00"))
            if published.tzinfo is None:
                continue
            published = published.astimezone(KST)
        except (ValueError, TypeError, AttributeError):
            continue
        if item.get("id") in ids and start <= published.date() <= end:
            items.append({"title": clean(snippet.get("title")), "description": clean(snippet.get("description")),
                          "source_url": "https://www.youtube.com/watch?v=" + item["id"],
                          "published_at": published.isoformat(), "collected_at": now(),
                          "source_name": clean(snippet.get("channelTitle")), "source_type": "youtube",
                          "date_basis": "video_uploaded_at"})
    return items


def result(request, module):
    stamp = now()
    return {"schema_version": "0.1", "request_id": request.get("request_id", "unknown"),
            "module": module, "status": "failed", "started_at": stamp, "finished_at": stamp,
            "query_context": {"mode": "live_search", "query_log": []}, "summary": "자료 미확보",
            "insights": [], "sources": [], "warnings": [], "errors": []}


def collect(output, provider, query, start, end):
    provider_name = getattr(provider, "__name__", "search_provider")
    if any(e.get("provider") == provider_name and
           (e.get("http_status") == 429 or e.get("code") in
            ("OFFLINE_MODE", "MISSING_NAVER_CREDENTIALS", "MISSING_YOUTUBE_API_KEY"))
           for e in output["errors"]):
        output["query_context"]["query_log"].append({"provider": provider_name, "query": query,
                                                    "skipped": "provider_unavailable_this_run"})
        return []
    try:
        items = provider(query, start, end)
        output["query_context"]["query_log"].append({"provider": provider_name, "query": query,
                                                    "finished_at": now(), "item_count": len(items)})
        return items
    except SearchError as exc:
        output["errors"].append({"code": exc.code, "provider": provider_name, "http_status": exc.status})
        output["query_context"]["query_log"].append({"provider": provider_name, "query": query,
                                                    "finished_at": now(), "error_code": exc.code})
        return []
