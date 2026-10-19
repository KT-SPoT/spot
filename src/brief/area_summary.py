"""Describe sourced place context without substituting a customer profile."""
import re


def area_summary(brief):
    if brief.get('regional_synthesis',{}).get('version')=='regional-analysis-v2' and brief.get('regional_synthesis',{}).get('performed') and brief['regional_synthesis'].get('area_summary_applied', True):
        summary=brief.get('overview',{}).get('area_summary')
        if isinstance(summary,str) and summary.strip():return summary
    signals = brief.get('unique_local_signals', [])
    places = [c['place'] for c in signals if c.get('type') == 'local_place' and c.get('sources') and c.get('place')]
    if places:
        groups = {}
        for place in places:
            groups.setdefault(place['category'], []).append(place)
        clauses = []
        for category, rows in list(groups.items())[:4]:
            names = '·'.join(p['name'] for p in sorted(rows, key=lambda p: p['distance_m'])[:2])
            clauses.append(f"{category} 시설로 {names}")
        return '매장 주변에서 ' + ', '.join(clauses) + ' 등이 검색됩니다.\n서로 다른 시설의 접근 환경을 함께 살펴볼 수 있는 지역입니다. 시설 목록은 검색된 장소이며, 방문량이나 전체 시설 분포를 뜻하지 않습니다.'
    facility = next((c for c in signals if c.get('module') == 'quant'
                     and c.get('title') == '최다 주요시설 유형' and c.get('value') and c.get('sources')), None)
    parts = []
    if facility:
        parts.append(f"선택한 조사 영역의 주요시설 중 {facility['value']} 유형이 가장 많이 집계된 지역입니다.")
    # Keep dated news as reported local context, not a permanent neighborhood trait.
    local = [c for c in brief.get('local_changes', []) if c.get('sources')]
    background = [c for c in signals if c.get('module') == 'local'
                  and c.get('evidence_role') == 'background' and c.get('sources')]
    seen = set()
    for card in (background + local):
        title = re.sub(r'\s+', ' ', str(card.get('title') or '')).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        date = str(card.get('published_at') or card['sources'][0].get('published_at') or '')[:10]
        label = f"{date} 보도" if date else '지역 보도'
        parts.append(f"{label}에서는 ‘{title}’ 소식을 다룹니다.")
        if len(seen) == 2:
            break
    return '\n'.join(parts) or '선택한 매장 주변을 조사한 결과입니다. 아래 지도에서 조사 위치와 범위를 확인할 수 있습니다.'
