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
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit, urljoin
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
        self.image = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        marker = " ".join(str(attrs.get(k, "")) for k in ("id", "class", "itemprop")).lower()
        marked = tag == "article" or any(x in marker for x in ("articlebody", "article-body", "article_body", "article-view-content", "article_txt", "article_text", "article-content", "article_content", "news_body", "newsbody", "dic_area"))
        skip = tag in ("nav", "aside", "header", "footer", "style", "script", "noscript", "form", "title", "h1", "h2", "h3", "h4", "h5", "h6")
        parent_skip = any(s[2] for s in self.stack)
        if tag == "meta":
            image_key = (attrs.get("property") or attrs.get("name") or "").lower()
            if image_key == "og:image" or (image_key in ("twitter:image", "twitter:image:src") and not self.image):
                self.image = attrs.get("content") or self.image
            if attrs.get("property") in ("article:published_time", "og:article:published_time") or attrs.get("itemprop") == "datePublished":
                self.dates.append(attrs.get("content"))
            return
        if tag == "time" and attrs.get("datetime") and not parent_skip:
            self.dates.append(attrs["datetime"])
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
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo:
                    dates.add(parsed.astimezone(search.KST).date())
            except (ValueError, TypeError):
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


def context_evidence(blocks, anchor, store, start=None):
    """Classify article context without assigning nearby events to the store.

    A locality stem is used only with an explicit requested-area mention
    elsewhere in the same article. It is a textual link, not a geofence.
    """
    text = " ".join(blocks)
    anchor_present = search.normalized(anchor) in search.normalized(text)
    stem = re.sub(r"(?:국제)?신도시$|[동읍면]$", "", anchor)
    stem = stem if len(stem) >= 2 else anchor
    districts = re.findall(r"(?:^|\s)([가-힣]+[구군])(?:\s|$)", store.get("address") or "")
    district_present = any(d in text for d in districts)
    sentences = [s.strip() for block in blocks for s in re.split(r"(?<=[.!?。])\s+", block) if 30 <= len(s.strip()) <= 1000]
    historical, direct = [], []
    for sentence in sentences:
        exact = search.normalized(anchor) in search.normalized(sentence)
        local_entity = anchor_present and bool(re.search(re.escape(stem) + r"(?:국제)?(?:지구|\d*호\s*근린공원|\s*중앙공원)", sentence))
        if not (exact or local_entity):
            continue
        if re.search(r"루머|소문|거짓|확인되지|부인", sentence):
            continue
        mixed = bool(re.search(r"[가-힣]{2,8}동(?:에서|에서는|일원)|다른 지역", sentence)) and not exact
        past = bool(start and (any(int(y) < start.year for y in re.findall(r"(20\d{2})\s*년", sentence)) or
                    any((int(y), int(m)) < (start.year, start.month) for y, m in re.findall(r"(20\d{2})\s*년\s*(\d{1,2})\s*월", sentence))))
        # Keep historical/property comparisons as background, never recent move-ins.
        if past or re.search(r"20\d{2}\s*년.*입주|거래|매매가|시세|가격|기존|비교", sentence):
            historical.append(sentence)
        if not mixed and re.search(r"실시계획|개발계획|공사.*(?:지연|차질)|협의.*지연|선착순|공급에 나|개관|개통|착공|준공|조성.*(?:예정|계획)|규정.*(?:삭제|폐지)", sentence):
            # Old dates alone do not promote a background comparison to a change.
            if not past and not re.search(r"20\d{2}\s*년.*입주", sentence):
                direct.append(sentence)
    if direct:
        role, sentence = "direct_change", direct[0]
        note = "요청 지역명이 등장하는 원문에서 관련 사업·시설 문맥을 연결했습니다. 지역명 대응과 실제 사업 범위는 추가 확인이 필요합니다."
    elif historical:
        role, sentence = "background", historical[0]
        note = "지역 여건·기존 정책·과거 사례·가격 비교를 이해하기 위한 배경 자료입니다. 최근 입주나 고객 수요 증가의 근거로 사용하지 않습니다."
    elif district_present and re.search(r"교통|버스|노선|소각장|환경|주거|임대|아파트", text):
        role = "surrounding_context"
        candidates = [s for s in sentences if any(d in s for d in districts) and re.search(r"버스|노선|소각장|환경|주거|임대|아파트|대중교통", s)]
        sentence = candidates[0] if candidates else next((s for s in sentences if any(d in s for d in districts)), "")
        note = "점포와 같은 행정구역의 보조 맥락입니다. 실제 인접 거리·생활권 연결·점포 영향은 확인하지 않았습니다."
    else:
        return None
    if not sentence:
        return None
    plan_numbers = set(re.findall(r"(\d{1,3})\s*차", text))
    event_key = None
    if role == "direct_change" and "실시계획" in text and len(plan_numbers) == 1 and anchor_present and stem + "지구" in text:
        event_key = hashlib.sha256((anchor + "|실시계획|" + next(iter(plan_numbers))).encode()).hexdigest()
    stage = classify_stage(sentence) if role == "direct_change" else "not_applicable"
    if role == "direct_change" and re.search(r"변경\s*승인.*완료|실시계획.*변경을?\s*마무리|실시계획.*변경.*완료", sentence):
        stage = "reported_plan_approval"
    at = sentence.find(anchor)
    if at < 0:
        at = sentence.find(stem)
    excerpt = sentence[max(0, at - 15):max(0, at - 15) + 120]
    return {"evidence_role": role, "context_note": note, "excerpt": excerpt,
            "change_state": stage, "event_key": event_key,
            "evidence_fingerprint": hashlib.sha256(search.normalized(sentence).encode()).hexdigest(),
            "classification_basis": "requested_area_article_context" if anchor_present else "same_administrative_district"}


def verify_source(item, anchor, start, end, store=None):
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
    # Do not identify a same-named neighborhood in another metropolitan city.
    address = (store or {}).get('address') or ''
    cities = ('서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종')
    requested_city = next((city for city in cities if address.startswith(city)), None)
    article_text = ' '.join(blocks) + ' ' + item.get('title', '')
    if requested_city and requested_city not in article_text and any(city in item.get('title','') for city in cities if city != requested_city):
        verification.update(status='rejected', reason='OTHER_CITY_SAME_NEIGHBORHOOD')
        return verification
    if parser.image:
        image_url = urljoin(resolved, parser.image)
        try:
            validate_url(image_url)
            if image_url.startswith('https://'):
                verification['thumbnail_url'] = image_url
        except search.SearchError:
            pass
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
        contextual = context_evidence(blocks, anchor, store, start) if store is not None else None
        if contextual:
            verification.update(contextual, status="context_corroborated", reason="ARTICLE_CONTEXT_NOT_EVENT_CONFIRMATION",
                                date_basis="article_published_at" if publication else item.get("date_basis"),
                                full_text_verified=False)
        else:
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
    if store is not None:
        contextual = context_evidence(blocks, anchor, store, start)
        if contextual:
            verification.update(evidence_role="direct_change", event_key=contextual.get("event_key"),
                                context_note=contextual["context_note"], classification_basis="same_sentence")
        else:
            verification["evidence_role"] = "direct_change"
        if verification["status"] == "candidate":
            verification["status"] = "context_corroborated"
            verification.setdefault("context_note", "원문 문장은 확인했지만 원문 게시일 또는 본문 영역 확인이 부족합니다. 날짜·사업 범위의 추가 확인이 필요합니다.")
    return verification
