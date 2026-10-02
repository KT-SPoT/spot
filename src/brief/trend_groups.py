"""Conservative related-coverage groups, never verified independent events."""
import re
from datetime import date

GENERIC = {"팝업", "팝업스토어", "체험", "체험형", "스마트폰", "갤럭시", "아이폰",
           "삼성전자", "폴드", "플립", "시리즈", "제품", "신제품", "테마파크", "챌린지", "미니게임", "포토존"}


def _words(text):
    return set(re.findall(r"[a-z0-9가-힣]+", text.lower())) if isinstance(text, str) else set()


def _day(case):
    try:
        return date.fromisoformat(case.get("published_at", "")[:10])
    except (ValueError, TypeError):
        return None


def group_coverage(cases, product=""):
    """Same day + leading brand + quoted distinctive name. Missing signals stay separate.

    Quoted names are inferred only from the supplied candidates, with generic
    product/category words removed. No chain merging; compare to the representative.
    This is a presentation grouping, not proof that reports describe one event.
    """
    quoted = set()
    for case in cases:
        for phrase in re.findall(r"['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”]", (case.get("event_name") or "") + ' ' + (case.get('observation') or case.get('description') or '')):
            quoted.update(_words(phrase))
    anchors = {word for word in quoted - GENERIC - _words(product)
               if (len(word) >= 3 and not any(char.isdigit() for char in word))
               or re.fullmatch(r'\d+색', word)}

    def matches(left, right):
        day = _day(left)
        if day is None or day != _day(right):
            return False
        if left.get("location") != right.get("location"):
            return False
        a, b = left.get("event_name") or "", right.get("event_name") or ""
        if a and a == b:
            return True
        lead_a, lead_b = re.match(r"[a-zA-Z0-9가-힣]+", a), re.match(r"[a-zA-Z0-9가-힣]+", b)
        if not lead_a or not lead_b or lead_a[0].lower() != lead_b[0].lower():
            return False
        details_a = a + ' ' + (left.get('observation') or left.get('description') or '')
        details_b = b + ' ' + (right.get('observation') or right.get('description') or '')
        return bool(anchors & _words(details_a) & _words(details_b))

    groups = []
    for case in cases:
        group = next((group for group in groups if matches(group[0], case)), None)
        if group is None:
            groups.append([case])
        else:
            group.append(case)
    return groups
