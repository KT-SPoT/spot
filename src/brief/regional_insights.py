"""Sourced regional observations and planning lenses, before case selection."""
import math
import re

AGES={'teens':'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대','60_plus':'60대 이상'}
DAYS=dict(zip(('mon','tue','wed','thu','fri','sat','sun'),('월요일','화요일','수요일','목요일','금요일','토요일','일요일')))


def peaks(card, labels):
    values=[(k,v.get('share_pct')) for k,v in card.get('shares',{}).items() if k in labels and isinstance(v,dict)]
    values=[(k,v) for k,v in values if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<v<=100]
    maximum=max((v for _,v in values),default=0)
    return [(k,v) for k,v in values if v==maximum]


def regional_insights(quant, local=()):
    rows=[]
    usable=[c for c in quant if c.get('sources')]
    def add(title, observation, interpretation, question, cards, terms=(), mechanisms=()):
        rows.append({'kind':'research_question','title':title,'statement':f'{observation} {interpretation} {question}',
                     'observation':observation,'interpretation':interpretation,'question':question,
                     'basis':cards,'search_terms':list(terms),'mechanisms':list(mechanisms)})
    age=next((c for c in usable if c.get('population_kind')=='sales' and
              (c.get('distribution_kind')=='age' or '연령' in c.get('title','')) and peaks(c,AGES)),None)
    if age:
        text=' / '.join(f'{AGES[k]} {v:g}%' for k,v in peaks(age,AGES))
        add('매출 구성에서 먼저 살펴볼 연령 구간',f'매출액 연령 구성에서 {text}가 가장 높습니다.',
            '홍보 기획의 우선 검토 구간으로 삼을 수 있습니다.',
            '이 구간에서 설명할 제품 사용 장면을 기획 단계에서 비교합니다.',[age])
    for axis,labels in (('time',{'05_09':'05~09시','09_12':'09~12시','12_14':'12~14시','14_18':'14~18시','18_23':'18~23시','23_05':'23~05시'}),('day',DAYS)):
        card=next((c for c in usable if c.get('population_kind')=='sales' and c.get('distribution_kind')==axis and peaks(c,labels)),None)
        if not card:continue
        winners=peaks(card,labels)
        observed=' / '.join(f'{labels[k]} {v:g}%' for k,v in winners)
        if axis=='time':
            evening=any(k=='18_23' for k,v in winners)
            add('매출이 집중되는 시간의 체험 접점',f'시간대별 매출액 구성은 {observed}가 가장 높습니다.',
                '이 시간대를 체험 접점의 운영 후보로 살펴볼 수 있습니다.',
                '설명 중심과 직접 비교하는 참여 방식을 이 시간대의 운영 후보로 검토합니다.',[card],
                ('저녁 팝업 체험' if evening else '직접 비교 체험 팝업',),('direct_product_trial','mission_journey','photo_sharing'))
        else:
            weekend=any(k in ('sat','sun') for k,v in winners)
            add('요일별 매출 구성과 행사 운영 후보',f'요일별 매출액 구성은 {observed}가 가장 높습니다.',
                '요일별 구성은 행사일 후보를 좁히는 관측 기준입니다.',
                '이 요일에 어떤 참여 접점을 운영할지 비교합니다.',[card],
                ('주말 체험 행사' if weekend else '평일 체험 행사',),('direct_product_trial','mission_journey'))
    for card in local:
        if card.get('type') == 'local_place':continue
        if not card.get('sources'):continue
        text=str(card.get('evidence') or card.get('statement') or '')
        if not text:continue
        title=card.get('title') or '지역 보도'
        surrounding=card.get('evidence_role') in ('surrounding_context','background')
        prefix='주변 행정구역 보도' if surrounding else '지역 보도'
        if re.search(r'통행|개통|교통|도로 정비',text):
            add('이동 경로와 매장 발견 접점',f'{prefix} 「{title}」: {text}',
                '보도된 이동 경로를 매장 위치 안내와 함께 살펴볼 수 있습니다.',
                '길찾기·방문 동선 안내를 체험의 첫 접점으로 연결할지 검토합니다.',[card],
                ('스탬프 투어 체험 행사',),('mission_journey',))
        elif re.search(r'개관|개점|신설|입주|주거',text):
            add('보도된 시설·주거 변화와 생활 장면',f'{prefix} 「{title}」: {text}',
                '보도된 사업 단계와 시설의 용도를 생활 장면을 정하는 참고 자료로 활용합니다.',
                '생활 속 사용 장면을 직접 비교하는 체험 구성을 검토합니다.',[card],
                ('생활 체험 팝업',),('direct_product_trial',))
        if len(rows)>=6:break
    return rows[:6]


def case_connections(case, insights, actions):
    """A cohort word alone never supplies a transferable regional rationale."""
    output=[]
    for lens in insights:
        for mechanism,action,scene in actions:
            if mechanism not in lens.get('mechanisms',[]):continue
            refs=list({(c.get('module','quant'),s['source_id']):{'module':c.get('module','quant'),'source_id':s['source_id']}
                       for c in lens['basis'] for s in c.get('sources',[]) if s.get('source_id')}.values())
            output.append({'kind':'research_question','mechanism':mechanism,
                           'statement':f"지역 관측: {lens['observation']} 사례에서 참고할 행동: {action}. 연결 단서: {lens['question']} 이 사례의 {action}을 비교 자료로 사용합니다.",
                           'context_source_refs':refs})
    return output[:4]
