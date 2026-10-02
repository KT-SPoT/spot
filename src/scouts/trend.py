"""Context-aware live Trend discovery; historical references never imply success."""
import json
import re
from pathlib import Path
from datetime import date
from copy import deepcopy
from src.scouts import search_runtime as search
from src.scouts import trend_relevance as relevance

PATTERNS = {
    "mission_journey": ("미션 기반 참여 동선", ("미션", "스탬프", "단서")),
    "direct_product_trial": ("직접 제품·기능 체험", ("체험", "시연", "hands-on")),
    "worldbuilding_exploration": ("세계관·테마 공간 탐색", ("세계관", "테마 공간", "테마존")),
    "game_interaction": ("게임·도전 참여", ("미니게임", "미니 게임", "게임 체험", "챌린지", "대결")),
    "photo_sharing": ("촬영·결과물 공유", ("포토존", "촬영", "인증샷", "사진", "공유")),
    "food_discovery": ("시식·취향 탐색", ("시식", "테이스팅", "맛보기")),
    "collectible_reward": ("참여·수집 보상", ("굿즈", "수집", "한정판", "리워드")),
}
OFFLINE_CUES = ("팝업", "체험존", "체험 공간", "체험공간", "오프라인 행사", "전시회", "전시관", "행사장", "체험관", "축제", "페스티벌", "지역 행사", "지역행사")
AGE_LABELS = {"under_10":"10세 미만", "teens":"10대", "20s":"20대", "30s":"30대", "40s":"40대", "50s":"50대", "60_plus":"60대"}
MAX_QUERIES = 3


def product_alias(product):
    alias = product
    for old,new in (("galaxy","갤럭시"),("fold","폴드"),("flip","플립"),("iphone","아이폰")):
        alias = alias.lower().replace(old,new)
    return alias


def build_queries(request, context):
    # Category breadth is independent of gender. One broad query remains ungated
    # by cohort words; demographics guide discovery, never establish preference.
    queries = ['게임 팝업 체험', '음식 팝업 체험', '지역 축제 참여 체험']
    age = next((s.get('dominant_age') for s in context.get('population_signals',[]) if s.get('population_kind')=='floating_population'),None)
    if age in AGE_LABELS:
        queries[-1] += ' ' + AGE_LABELS[age]
    sales_age = next((s.get('dominant_age') for s in context.get('population_signals',[]) if s.get('population_kind')=='sales'),None)
    if sales_age in AGE_LABELS:
        queries[1] += ' ' + AGE_LABELS[sales_age]
    return list(dict.fromkeys(queries))[:MAX_QUERIES]


def event_category(text):
    lowered = text.lower()
    if any(w in lowered for w in ('게임', '게이밍', 'game', '챌린지')):
        return 'game'
    if any(w in lowered for w in ('음식', '푸드', '디저트', '시식', '라면', '커피', '맛보기')):
        return 'food'
    if any(w in lowered for w in ('축제', '페스티벌', '지역 행사', '지역행사')):
        return 'festival'
    return 'other'


def diversified_references(cases, limit=5):
    selected, seen = [], set()
    for case in cases:
        category = case['event_category']
        if category not in seen:
            selected.append(case)
            seen.add(category)
        if len(selected) >= limit:
            return deepcopy(selected)
    selected.extend(c for c in cases if c not in selected)
    return deepcopy(selected[:limit])


def adaptation_hypotheses(tags, product):
    # Applications are questions, not demonstrated appeal or device specs.
    applications = {
        'mission_journey': '미션·스탬프 동선을 여러 기능을 직접 비교하는 매장 체험에 응용할 수 있을까?',
        'game_interaction': '짧은 게임·도전 구조를 기기 조작과 사용 경험을 비교하는 체험에 응용할 수 있을까?',
        'photo_sharing': '촬영·결과물 공유 구조를 카메라 체험과 결과물 비교에 응용할 수 있을까?',
        'food_discovery': '시식의 취향 비교 방식을 기기 사용 경험 비교나 음식 촬영 체험에 응용할 수 있을까?',
        'collectible_reward': '수집·참여 보상 구조를 기능 탐색의 참여 동기로 응용할 수 있을까?',
        'worldbuilding_exploration': '테마 공간의 탐색 구조를 일상 사용 장면별 매장 체험에 응용할 수 있을까?',
        'direct_product_trial': '직접 사용·비교 구조를 매장 제품 체험에 응용할 수 있을까?',
    }
    return [{'kind': 'research_question', 'mechanism': tag,
             'statement': f'{product}: {applications[tag]} 실제 지원 기능과 고객 반응은 추가 조사.'}
            for tag in tags if tag in applications][:3]


def audience_hypothesis(context):
    labels = []
    for profile in context.get('population_signals', []):
        cohort = [AGE_LABELS.get(profile.get('dominant_age')),
                  {'male': '남성', 'female': '여성'}.get(profile.get('dominant_gender'))]
        if any(cohort):
            labels.append(profile['population_kind'] + ': ' + '/'.join(c for c in cohort if c))
    return (('Quant가 전달한 인구·매출 구성 (' + '; '.join(labels) + ')을 바탕으로 이 참여 방식에 호응할지 조사. '
             '인구 구성은 관측값이며 관심·선호는 탐색 가설입니다.') if labels else
            '고객층 자료가 없어 특정 성별·연령의 선호를 정하지 않고 참여 방식의 응용 가능성을 조사합니다.')


def context_fit(text, context):
    reasons, refs, notes = [], [], []
    for signal in context.get('population_signals',[]):
        age = AGE_LABELS.get(signal.get('dominant_age'))
        gender = {'male':'남성','female':'여성'}.get(signal.get('dominant_gender'))
        hits = [word for word in (age,gender) if word and word in text]
        if hits:
            reasons.append('인구 신호와 후보 메타데이터의 표현 겹침: ' + '/'.join(hits) + ' (' + signal['population_kind'] + ')')
            refs.extend({'module':'quant','source_id':sid} for sid in signal.get('source_ids',[]))
            notes.append('실제 행사 참여자의 성별·연령을 확인한 것은 아닙니다.')
    for signal in context.get('local_signals',[]):
        words = {w for w in re.findall(r'[가-힣]{2,12}',signal.get('title','') + ' ' + signal.get('evidence',''))
                 if w in ('공원','교통','버스','임대','주거','개발','입주','환경','문화','학교')}
        hits = sorted(w for w in words if w in text)
        if hits:
            reasons.append('Local 자료와 후보 메타데이터의 표현 겹침: ' + '/'.join(hits))
            refs.extend({'module':'local','source_id':sid} for sid in signal.get('source_ids',[]))
            notes.append('같은 단어가 등장해도 동일 지역·실제 생활권 영향·수요를 확정하지 않습니다.')
    refs = list({(r['module'],r['source_id']):r for r in refs}.values())
    return min(len(reasons),2), reasons, refs, list(dict.fromkeys(notes))


def library_references(request,start,end):
    records=json.loads(Path(__file__).with_name('trend_reference_library.json').read_text(encoding='utf-8'))
    records=[r for r in records if start <= date.fromisoformat(r['published_at']) <= end]
    selected=relevance.select_reference_cases(records,request,limit=3)
    return [{'case_id':'LIB-'+r['case_id'],'origin':'historical_reference_library',
             'case_name':r['event_name'],'source_url':r['verification_url'],
             'published_at':r['published_at'],'recorded_verification_at':r['verified_at'],
             'recorded_verification_status':r.get('verification_status'),'rechecked_during_run':False,
             'note':'과거 참고 라이브러리입니다. 이번 검색 근거나 성공 판정·반복 패턴 수에 포함하지 않습니다.'} for r in selected]


def build_patterns(cases):
    patterns=[]
    for key,(name,_) in PATTERNS.items():
        examples=[i for i in cases if key in i['taxonomy_tags']]
        if len(examples)>=2:
            patterns.append({'pattern_id':key,'name':name,
                'description':'검색 메타데이터에서 관련 표현이 반복됨. 실제 경험 구조·독립 행사 여부·적합성은 확인 필요.',
                'evidence_basis':'search_metadata','verification_status':'candidate','evidence_count':len(examples),
                'example_case_ids':[i['case_id'] for i in examples],
                'example_source_ids':[sid for i in examples for sid in i['source_ids']]})
    return patterns


def run_trend_scout(request, *, context=None):
    output=search.result(request,'trend')
    output.update(patterns=[],reference_cases=[],reference_patterns=[],reference_library=[])
    try:
        start,end,days=search.window(request)
    except (ValueError,TypeError):
        output['errors'].append({'code':'INVALID_RESEARCH_WINDOW'})
        return output
    product=(request.get('campaign') or {}).get('product')
    if not isinstance(product,str) or not product.strip():
        output['errors'].append({'code':'MISSING_CAMPAIGN_PRODUCT'})
        return output
    context=deepcopy(context) if isinstance(context,dict) and context.get('request_id')==request.get('request_id') else {}
    queries=build_queries(request,context)
    output['reference_library']=library_references(request,start,end)
    output['query_context'].update(reference_date=end.isoformat(),lookback_start=start.isoformat(),lookback_days=days,
        product=product,search_queries=queries,max_queries_per_provider=MAX_QUERIES,
        scope='전국·다업종 오프라인 체험; 고객층 맥락과 매장 응용 가능성 탐색',
        upstream_context=context, relevance_mode='nationwide_experience_transfer_with_audience_context')
    output['warnings']=['SEARCH_METADATA_ONLY_EVENTS_UNVERIFIED','YOUTUBE_CONTENT_NOT_WATCHED',
        '후보자료 수는 독립 행사 수가 아닙니다. 실제 체험 구조·참여자·효과를 확인해야 합니다.',
        'NAVER_DATE_IS_PROVIDED_AT','DISTINCT_SOURCES_NOT_DISTINCT_EVENTS','BOUNDED_SEARCH_NOT_EXHAUSTIVE',
        'HISTORICAL_LIBRARY_NOT_LIVE_EVIDENCE']
    output['warnings'].extend(context.get('limitations',[]))
    if not context.get('population_signals'):
        output['warnings'].append('QUANT_POPULATION_CONTEXT_UNAVAILABLE')
    if not context.get('local_signals'):
        output['warnings'].append('LOCAL_CONTEXT_UNAVAILABLE')
    by_url={}
    for provider in (search.news,search.videos):
        for query in queries:
            for item in search.collect(output,provider,query,start,end):
                url=item['source_url']
                if url not in by_url:
                    by_url[url]=dict(item,matched_queries=[])
                if query not in by_url[url]['matched_queries']:
                    by_url[url]['matched_queries'].append(query)
    ranked=[]
    phone=any(w in product.lower() for w in ('galaxy','iphone','갤럭시','아이폰','스마트폰'))
    for item in by_url.values():
        text=item['title']+' '+item['description']
        title_match,_=relevance.find_product_match(item['title'].lower(),item['title'].lower().replace(' ',''),product)
        category=phone and any(w in item['title'].lower() for w in ('스마트폰','갤럭시','아이폰','galaxy','iphone'))
        cue_text=item['title'] if item['source_type']=='news' else text
        if not any(w in cue_text.lower() for w in OFFLINE_CUES):
            continue
        if any(w in item['title'].lower() for w in ('최저가', '구매링크', '구매 링크', '언박싱', 'unboxing')):
            continue
        mechanisms = [key for key, (_, words) in PATTERNS.items()
                      if any(relevance.contains_experience_keyword(w, text.lower(), text.lower().replace(' ', '')) for w in words)]
        score_delta,why,refs,limits=context_fit(text,context)
        # Product/geographic match never determines inclusion or priority.
        ranked.append(dict(item,score=3+min(len(mechanisms),3)+score_delta,
            product_match_level=title_match,relevance_reasons=['전국 오프라인 체험 후보', '체험 방식 표현: ' + ', '.join(mechanisms)],
            context_fit_reasons=why,context_source_refs=refs,context_limitations=limits,
            request_relevance='same_product' if title_match=='exact' else 'adjacent_category' if category else 'cross_industry_transfer'))
    ranked.sort(key=lambda i:(-i['score'],i['source_url']))
    provider_counts={}
    for item in ranked:
        kind=item['source_type']
        if provider_counts.get(kind,0)>=10:
            continue
        provider_counts[kind]=provider_counts.get(kind,0)+1
        n=len(output['insights'])+1;sid,cid=f'S-T-{n:03}',f'T-{n:03}'
        text=item['title']+' '+item['description']
        tags=[key for key,(_,words) in PATTERNS.items() if any(relevance.contains_experience_keyword(w,text.lower(),text.lower().replace(' ','')) for w in words)]
        output['sources'].append({k:item[k] for k in ('source_url','source_name','source_type','published_at','collected_at','date_basis') if k in item} | {'source_id':sid,'title':item['title'],'verification':{'method':'search_metadata','event_verified':False}})
        why=['전국 체험 사례의 참여 방식을 매장에 응용할 가능성을 탐색하는 후보입니다.']+item['context_fit_reasons']
        refs = item['context_source_refs'] + [{'module': 'quant', 'source_id': sid}
            for profile in context.get('population_signals', []) for sid in profile.get('source_ids', [])]
        refs = list({(ref['module'], ref['source_id']): ref for ref in refs}.values())
        output['insights'].append({'case_id':cid,'type':'experiential_marketing_candidate','event_name':item['title'],
            'observation':item['description'],'published_at':item['published_at'],'brand':None,'location':None,
            'source_ids':[sid],'taxonomy_tags':tags,'verification_status':'candidate',
            'request_relevance':item['request_relevance'],'product_match_level':item['product_match_level'],
            'reference_priority_score':item['score'],'fit_signals':item['relevance_reasons'],
            'context_source_refs':refs,'why_relevant':why,
            'event_category':event_category(text), 'audience_hypothesis':audience_hypothesis(context),
            'adaptation_hypotheses':adaptation_hypotheses(tags,product),
            'limitations':['원문·영상·실제 행사 여부와 대상 고객은 확인하지 않았습니다.','인구 구성과 단어 겹침은 효과·취향·수요를 증명하지 않습니다.']+item['context_limitations'],
            'origin':'live_search_candidate'})
    output['reference_cases']=diversified_references(output['insights'])
    output['patterns']=build_patterns(output['insights'])
    output['reference_patterns']=build_patterns(output['reference_cases'])
    output['status']='partial' if output['insights'] else 'failed'
    output['summary']=f"전국·다업종 검색 후보 {len(output['insights'])}건 중 참고 후보 {len(output['reference_cases'])}건. 고객층 연결·매장 응용은 조사 가설이며 실제 호응은 미확인."
    output['finished_at']=search.now()
    return output
