"""Bounded planning questions from separate observations and reported actions.

No preference assignments, new evidence, provider calls or operational plans.
"""
import math
import re

AGES = {'under_10':'10세 미만', 'teens':'10대', '20s':'20대', '30s':'30대',
        '40s':'40대', '50s':'50대', '60_plus':'60대 이상'}


def reported_actions(case):
    text = str(case.get('observation') or '')
    name = str(case.get('event_name') or '')
    if not case.get('sources') or not text or ('...' in text and ('□' in text or '브리핑' in name)):
        return []
    tags = {h.get('mechanism') for h in case.get('adaptation_hypotheses', []) if isinstance(h, dict)}
    tags.update(case.get('taxonomy_tags', []))
    actions = []
    # A category alone (or the word 체험 alone) does not establish an action.
    if 'photo_sharing' in tags and re.search(r'촬영|사진|영상', text) and re.search(r'공유|SNS|소개|게시', text):
        promoter = bool(re.search(r'홍보대사|홍보활동|개인 SNS', name+' '+text))
        actions.append(('photo_sharing', '홍보자가 현장을 촬영해 소개한 방식' if promoter else '촬영 결과를 공유하는 방식',
                        '사진 촬영·정리·전송 등 실제 사용 과제를 보여주는 체험'))
    if 'collectible_reward' in tags and re.search(r'굿즈|소장|기념품|수집', text) and re.search(r'구매|판매|증정|제공|소장|수집', text):
        actions.append(('collectible_reward', '관련 물건을 구매·소장하도록 연결한 방식',
                        '기능 체험 결과를 완료 카드·사진 결과물 같은 가져갈 물건으로 연결하는 접점'))
    if 'direct_product_trial' in tags and re.search(r'직접 (?:사용|체험)|게임을 체험|시연|써보|비교', text):
        actions.append(('direct_product_trial', '직접 사용·시연·비교하는 방식', '스마트폰 기능을 직접 써보고 차이를 비교하는 체험'))
    if 'mission_journey' in tags and re.search(r'미션|스탬프', text) and re.search(r'수행|완료|모으|달성', text):
        actions.append(('mission_journey', '과제를 수행하고 완료 결과를 확인하는 방식', '스마트폰 기능 비교를 작은 사용 과제와 완료 결과로 보여주는 체험'))
    return actions


def connections(case, quant):
    """Existing adaptation_hypotheses shape, with cited observations kept separate."""
    actions = reported_actions(case)
    if not actions:
        return []
    usable = [c for c in quant if c.get('sources')]
    def peak(population):
        rows = []
        for card in usable:
            if card.get('population_kind') != population or '연령' not in str(card.get('title', '')):
                continue
            values = [(k, v.get('share_pct')) for k, v in card.get('shares', {}).items()
                      if k in AGES and isinstance(v, dict)]
            values = [(k,v) for k,v in values if isinstance(v,(int,float)) and not isinstance(v,bool)
                      and math.isfinite(v) and 0 <= v <= 100]
            maximum = max((v for _,v in values), default=0)
            winners = [(k,v) for k,v in values if v == maximum and v > 0]
            if len(winners) == 1:rows.append((card, *winners[0]))
        return rows[0] if rows else None
    sales, flow, worker = peak('sales'), peak('floating_population'), peak('worker_population')
    count = next((c for c in usable if c.get('title') == '직장인구' and isinstance(c.get('value'),(int,float))
                  and not isinstance(c['value'],bool) and math.isfinite(c['value']) and c['value'] > 0), None)
    contexts = []
    if sales:
        c,key,value = sales
        contexts.append(([c], f'매출액의 최다 연령 구간 {AGES[key]} {value:g}%',
                         f'{AGES[key]} 대상 기획 후보에서', '매출액 비중은 방문 고객 수·상품 선호가 아님.'))
    if flow and sales and flow[1] != sales[1]:
        contexts.append(([flow[0],sales[0]], f'유동인구 최다 연령 {AGES[flow[1]]} {flow[2]:g}% / 매출액 최다 연령 {AGES[sales[1]]} {sales[2]:g}%',
                         '매장 발견을 위한 도입과 상품 기능을 비교하는 접점을 서로 다른 후보로 나누어',
                         '두 모집단은 동일한 방문자 집단이 아니며 전환 관계도 확인되지 않음.'))
    elif worker and count:
        contexts.append(([count,worker[0]], f'직장인구 {count["value"]:,}명 / 직장인구 최다 연령 {AGES[worker[1]]} {worker[2]:g}%',
                         '업무 중 사용하는 기능과 생활 기능을 각각 보여주는 후보로', '근무·방문 목적이나 기능 선호를 조사한 자료는 아님.'))
    if count and (not worker or (flow and sales and flow[1] != sales[1])):
        contexts.append(([count], f'직장인구 {count["value"]:,}명 (기준 {count.get("reference_period") or "미제공"})',
                         '업무 중 사용하는 기능을 보여주는 후보로', '직장인구를 매출 연령대와 합쳐 특정 연령의 직장인 고객이라고 단정하지 않음.'))
    output = []
    for mechanism, action, scene in actions[:2]:
        for cards, observation, lens, limit in contexts[:3]:
            scope = ' / '.join(dict.fromkeys(f'{c.get("reference_period") or "기준월 미제공"} · {c.get("scope") or "범위 미제공"}' for c in cards))
            statement = (f'지역 관측: {observation} ({scope}). 사례에서 참고할 행동: {action}. '
                         f'연결 단서: {lens} {scene}을 참고할 수 있을까? {limit} '
                         '선호·호응·성과를 확인한 결과가 아닌 기획 질문.')
            refs = list(dict.fromkeys(s['source_id'] for c in cards for s in c.get('sources',[]) if s.get('source_id')))
            output.append({'kind':'research_question', 'mechanism':mechanism, 'statement':statement,
                           'context_source_refs':[{'module':'quant','source_id':sid} for sid in refs]})
    return output[:4]
