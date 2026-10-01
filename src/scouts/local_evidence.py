"""Bounded article retrieval and conservative, auditable Local text checks.

Reading a report corroborates what it says, not whether the event happened.
"""
import ipaddress
import hashlib
import json
import os
import re
import socket
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.scouts import search_runtime as search

MAX_BYTES = 1_500_000
CHANGE_RE = re.compile(r"개관|개통|입주|착공|준공|신설|건립|확충|공사|계획|승인|오픈")


def validate_url(url):
    """Only public HTTP(S) destinations, including on every redirect."""
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError()
        if parts.port not in (None, 80, 443):
            raise ValueError()
        if any(re.search(r"key|token|secret|password|credential", k, re.I)
               for k, _ in parse_qsl(parts.query)):
            raise ValueError()
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError()
    except (ValueError, OSError):
        raise search.SearchError("UNSAFE_OR_UNRESOLVED_SOURCE_URL") from None


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        count = getattr(req, "source_redirects", 0) + 1
        if count > 3:
            raise search.SearchError("SOURCE_REDIRECT_LIMIT")
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result:
            result.source_redirects = count
        return result


def fetch_article(url):
    if os.getenv("SPOT_SCOUT_MODE") == "offline":
        raise search.SearchError("OFFLINE_MODE")
    validate_url(url)
    try:
        request = Request(url, headers={"User-Agent": "SPOT-Research/0.1", "Accept": "text/html"})
        with build_opener(PublicRedirects()).open(request, timeout=8) as response:
            if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                raise search.SearchError("SOURCE_NOT_HTML")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise search.SearchError("SOURCE_TOO_LARGE")
            encoding = response.headers.get_content_charset()
            if not encoding:
                match = re.search(br"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", data[:4096], re.I)
                encoding = match.group(1).decode("ascii") if match else "utf-8"
            return data.decode(encoding), response.geturl()
    except HTTPError as exc:
        raise search.SearchError("SOURCE_HTTP_ERROR", exc.code) from None
    except (URLError, OSError, TimeoutError):
        raise search.SearchError("SOURCE_UNAVAILABLE") from None
    except (UnicodeError, LookupError):
        raise search.SearchError("SOURCE_ENCODING_UNSUPPORTED") from None


class ArticleParser(HTMLParser):
    """Extract marked article text or long paragraphs; ignore page furniture."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.marked = []
        self.paragraphs = []
        self.current = []
        self.dates = []
        self.json_scripts = []
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        marker = " ".join(str(attrs.get(k, "")) for k in ("id", "class", "itemprop")).lower()
        marked = tag == "article" or any(x in marker for x in ("articlebody", "article-body", "article_body", "article-view-content", "news_body", "newsbody", "dic_area"))
        skip = tag in ("nav", "aside", "header", "footer", "style", "script", "noscript", "form", "title", "h1", "h2", "h3", "h4", "h5", "h6")
        parent_skip = any(s[2] for s in self.stack)
        if tag == "meta":
            if attrs.get("property") in ("article:published_time", "og:article:published_time") or attrs.get("itemprop") == "datePublished":
                self.dates.append(attrs.get("content"))
            return
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json" and not parent_skip:
            self.script = []
        if tag in ("br", "hr"):
            self.current.append("\n")
            return
        if tag in ("img", "input", "link", "source", "wbr"):
            return
        if tag in ("p", "div", "article", "section"):
            self.flush()
        self.stack.append((tag, marked, skip))

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.json_scripts.append("".join(self.script))
            self.script = None
        if tag in ("p", "div", "article", "section"):
            self.flush()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if not any(s[2] for s in self.stack):
            self.current.append(data)

    def flush(self):
        text = re.sub(r"\s+", " ", " ".join(self.current)).strip()
        self.current = []
        if len(text) < 40 or any(s[2] for s in self.stack):
            return
        if any(s[1] for s in self.stack):
            self.marked.append(text)
        elif any(s[0] == "p" for s in self.stack):
            self.paragraphs.append(text)

    def document(self):
        self.flush()
        json_bodies = []
        def visit(node):
            if isinstance(node, list):
                for child in node:
                    visit(child)
            elif isinstance(node, dict):
                types = node.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                if isinstance(types, list) and any(t in ("NewsArticle", "Article", "ReportageNewsArticle") for t in types):
                    self.dates.append(node.get("datePublished"))
                    if isinstance(node.get("articleBody"), str):
                        json_bodies.append(search.clean(node["articleBody"]))
                for k, child in node.items():
                    if k == "@graph":
                        visit(child)
        for raw in self.json_scripts:
            try:
                visit(json.loads(raw))
            except (ValueError, RecursionError):
                continue
        if json_bodies:
            return json_bodies, "structured_article_body"
        return (self.marked, "marked_article_body") if self.marked else (self.paragraphs, "paragraph_fallback")


def publication_dates(values):
    dates = set()
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                dates.add(date.fromisoformat(value))
            else:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                dates.add(parsed.astimezone(search.KST).date() if parsed.tzinfo else parsed.date())
        except ValueError:
            continue
    return dates


def classify_stage(sentence):
    if re.search(r"아니|않았|못했|확인되지|거짓|루머|소문|부인|보류", sentence):
        return "unverified"
    # Future/conditional language always wins over a mention of completion.
    if re.search(r"예정|계획|목표|추진|전망|예상|예고|검토|경우|하면|가능|미정|지연|연기|취소", sentence):
        return "scheduled"
    if re.search(r"개관(?:했다|하였다)|개통(?:했다|하였다)|운영을? 시작|문을 열었다|오픈했다", sentence):
        return "reported_opening"
    if re.search(r"준공(?:했다|하였다|됐다)|입주(?:했다|완료)|착공(?:했다|하였다)|공사를? 시작", sentence):
        return "reported_construction_or_move_in"
    return "unverified"


def specific_change(sentence, anchor, start):
    if not 40 <= len(sentence) <= 700 or search.normalized(anchor) not in search.normalized(sentence) or not CHANGE_RE.search(sentence):
        return False
    # Recent articles can cite old move-ins as background, or a different
    # neighborhood's development in the same sentence as the requested area.
    if any(int(year) < start.year for year in re.findall(r"(20\d{2})\s*년", sentence)):
        return False
    for year, month in re.findall(r"(20\d{2})\s*년\s*(\d{1,2})\s*월", sentence):
        if (int(year), int(month)) < (start.year, start.month):
            return False
    other_areas = re.findall(r"[가-힣]+(?:신도시|시티)(?=\s|[의와과에는,])|[가-힣]{2,8}동(?=에서|에서는|에선|에는)", sentence)
    if any(search.normalized(area) != search.normalized(anchor) for area in other_areas):
        return False
    return classify_stage(sentence) != "unverified"


def verify_source(item, anchor, start, end):
    verification = {"method": "article_text_check", "checked_at": search.now(),
                    "full_text_verified": False, "event_verified": False, "status": "unavailable"}
    try:
        html, resolved = fetch_article(item["source_url"])
    except search.SearchError as exc:
        verification.update(reason=exc.code, http_status=exc.status)
        return verification
    parser = ArticleParser()
    parser.feed(html)
    blocks, extraction = parser.document()
    verification.update(resolved_url=resolved, extraction_method=extraction, status="unconfirmed")
    dates = publication_dates(parser.dates)
    if len(dates) > 1:
        verification["reason"] = "CONFLICTING_ARTICLE_DATES"
        return verification
    publication = next(iter(dates), None)
    verification["article_published_at"] = publication.isoformat() if publication else None
    if publication and not start <= publication <= end:
        verification.update(status="rejected", reason="ARTICLE_OUTSIDE_LOOKBACK")
        return verification
    # Region and change must occur in the same sentence, not unrelated page parts.
    matches = []
    for block in blocks:
        for sentence in re.split(r"(?<=[.!?。])\s+", block):
            if specific_change(sentence, anchor, start):
                matches.append(sentence)
    if not matches:
        verification["reason"] = "ARTICLE_REGION_CHANGE_NOT_CORROBORATED"
        return verification
    sentence = matches[0]
    stages = {classify_stage(s) for s in matches}
    stage = classify_stage(sentence) if len(stages) == 1 else "unverified"
    # Store a brief excerpt only, not a publisher's complete article.
    at = sentence.find(anchor)
    excerpt_start = max(0, at - 20)
    excerpt = sentence[excerpt_start:excerpt_start + 120]
    fingerprint = hashlib.sha256(search.normalized(sentence).encode("utf-8")).hexdigest()
    verification.update(excerpt=excerpt, evidence_fingerprint=fingerprint,
                        change_state=stage, date_basis="article_published_at" if publication else item.get("date_basis"),
                        status="text_corroborated" if publication and extraction != "paragraph_fallback" else "candidate",
                        full_text_verified=bool(publication and extraction != "paragraph_fallback"),
                        reason="SOURCE_REPORT_NOT_EVENT_CONFIRMATION")
    return verification
