"""Context-aware live Trend discovery; historical references never imply success."""
import json
import re
import os
from pathlib import Path
from datetime import date
from copy import deepcopy
from src.scouts import search_runtime as search
from src.scouts import trend_relevance as relevance
from src.brief.trend_groups import group_coverage
from src.scouts.trend_detail import check_detail, enrich_references

PATTERNS = {
    "mission_journey": ("미션 기반 참여 동선", ("미션", "스탬프", "단서")),
    "direct_product_trial": ("직접 제품·기능 체험", ("체험", "시연", "hands-on")),
    "worldbuilding_exploration": ("세계관·테마 공간 탐색", ("세계관", "테마 공간", "테마존")),
    "game_interaction": ("게임·도전 참여", ("미니게임", "미니 게임", "게임 체험", "챌린지", "대결")),
    "photo_sharing": ("촬영·결과물 공유", ("포토존", "촬영", "인증샷", "사진", "공유")),
    "food_discovery": ("시식·취향 탐색", ("시식", "테이스팅", "맛보기")),
    "collectible_reward": ("참여·수집 보상", ("굿즈", "수집", "한정판", "리워드")),
}
OFFLINE_CUES = ("팝업", "체험존", "체험 공간", "체험공간", "오프라인 행사", "전시", "공연", "박람회", "페어", "마라톤", "문화제", "행사장", "체험관", "축제", "페스티벌", "지역 행사", "지역행사")
AGE_LABELS = {"under_10":"10세 미만", "teens":"10대", "20s":"20대", "30s":"30대", "40s":"40대", "50s":"50대", "60_plus":"60대 이상"}
MAX_QUERIES = 3


def primary_profile(context):
    """Sales is the planning lens; population is an explicitly separate fallback."""
    profiles=[p for p in context.get('population_signals', []) if p.get('source_ids') and p.get('dominant_age') in AGE_LABELS]
    for kind in ('sales', 'floating_population', 'resident_population', 'worker_population'):
        profile=next((p for p in profiles if p.get('population_kind')==kind), None)
        if profile:return profile
    return {}


def product_alias(product):
    alias = product
    for old,new in (("galaxy","갤럭시"),("fold","폴드"),("flip","플립"),("iphone","아이폰")):
        alias = alias.lower().replace(old,new)
    return alias


def discovery_plan(request, context):
    """Broad + observed cohort + calendar; age is a search lens, not a preference."""
    campaign = request.get('campaign') or {}
    clean = lambda value: ' '.join(re.findall(r'[가-힣A-Za-z0-9]+', str(value or '')))
    product = clean(campaign.get('product'))[:60]
    purpose = clean(campaign.get('purpose'))
    defaults = ('제품 지역 맥락을 연결한 홍보 근거 탐색', '신제품 체험 행사 사전 리서치', '매장 지역 고객 맥락 리서치')
    # A verbatim user question is a search focus, never an observed customer fact.
    focus = '' if purpose in defaults else ' '.join(purpose.split()[:4])[:40]
    _, end, _ = search.window(request)
    targeted = ' '.join(part for part in (product, focus, '행사') if part)[:110] if product or focus else '오프라인 체험 행사'
    profile=primary_profile(context)
    age=AGE_LABELS.get(profile.get('dominant_age'))
    if age:targeted=f'{age} {targeted}'
    lenses=[l for l in context.get('regional_lenses',[]) if l.get('search_terms')]
    if lenses:
        return [
            {'role':'regional','query':lenses[0]['search_terms'][0],'reason':lenses[0]['observation']+' '+lenses[0]['question']},
            {'role':'audience' if age else 'experience','query':targeted,'reason':'별도의 연령 구성에 따른 전국 사례 탐색'},
            {'role':'regional' if len(lenses)>1 else 'timing',
             'query':lenses[1]['search_terms'][0] if len(lenses)>1 else f'{end.year} {end.month}월 축제',
             'reason':lenses[1]['observation']+' '+lenses[1]['question'] if len(lenses)>1 else '조사 기준월의 전국 행사 일정 탐색'},
        ]
    return [
        {'role':'broad', 'query':'팝업', 'reason':'업종을 미리 지정하지 않고 전국 행사 참고 사례 탐색'},
        {'role':'audience' if age else 'experience', 'query':targeted, 'reason':f"{profile.get('population_kind') or '고객층 미확보'} 기준의 전국 행사 탐색. 연령 언급은 선호나 실제 참여자 검증이 아님; 성별로 업종을 지정하지 않음"},
        {'role':'timing', 'query':f'{end.year} {end.month}월 축제', 'reason':'요청 자료 기준월의 전국 일정·행사 보도 탐색; 실제 행사 일정은 원문에서 확인'},
    ]


def build_queries(request, context):
    return list(dict.fromkeys(row['query'] for row in discovery_plan(request, context)))[:MAX_QUERIES]


def video_event_query(title):
    """Prefer a quoted event name over a long news headline."""
    phrases=re.findall(r"['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”]",title)
    names=[' '.join(re.findall(r'[가-힣A-Za-z0-9]+',p)) for p in phrases]
    names=[p for p in names if 4<=len(p)<=55 and len(p.split())<=6 and not re.fullmatch(r'\d+대(?: 이상)?',p)]
    if names:
        names.sort(key=lambda p:any(w in p for w in ('페스타','페스티벌','축제','팝업','전시')),reverse=True)
        return names[0]
    return ' '.join(re.findall(r'[가-힣A-Za-z0-9]+',title)[:6])[:70]


def event_category(title):
    # An event's industry is separate from its game/photo participation mechanic.
    lowered = title.lower()
    for category, words in (
            ('food', ('음식', '푸드', '디저트', '시식', '라면', '커피', '맛보기', '버거', '식품')),
            ('beauty', ('화장품', '뷰티', '코스메틱', '안티에이징')),
            ('festival', ('축제', '페스티벌', '지역 행사', '지역행사')),
            ('culture', ('문화', '콘텐츠', '캐릭터', '공연', '음악', '뮤지컬')),
            ('game', ('게임', '게이밍', 'game'))):
        if any(w in lowered for w in words):
            return category
    return 'other'


def diversified_references(cases, limit=5):
    groups = group_coverage([c for c in cases if c.get('evidence_role') != 'audience_context'])
    representatives = []
    for group in groups:
        representative = deepcopy(group[0])
        representative['related_case_ids'] = [c['case_id'] for c in group]
        representatives.append(representative)
    representatives.sort(key=lambda c:(-c.get('context_match_score',0),-c.get('reference_priority_score',0)))
    selected, seen = [], set()
    # Reserve space for context-linked cases before category coverage. Otherwise
    # one familiar example per industry can crowd out new cohort-query results.
    selected=[c for c in representatives if c.get('context_match_score',0)>0][:min(2,limit)]
    seen={c['event_category'] for c in selected}
    ordered = [c for c in representatives if c['event_category'] != 'other'] + [c for c in representatives if c['event_category'] == 'other']
    for case in ordered:
        category = case['event_category']
        if len(selected)>=limit:break
        if case not in selected and category not in seen:
            selected.append(case)
            seen.add(category)
        if len(selected) >= limit:
            return deepcopy(selected)
    selected.extend(c for c in representatives if c not in selected)
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
             'statement': f'{product + ": " if product else ""}{applications[tag]} 제품·기능 선택은 기획 단계에서 확인.'}
            for tag in tags if tag in applications][:3]


def audience_hypothesis(context):
    labels = []
    for profile in context.get('population_signals', []):
        cohort = [f"주요 연령 {AGE_LABELS[profile['dominant_age']]}" if profile.get('dominant_age') in AGE_LABELS else None,
                  f"주요 성별 { {'male': '남성', 'female': '여성'}[profile['dominant_gender']]}" if profile.get('dominant_gender') in ('male', 'female') else None]
        if any(cohort):
            labels.append(profile['population_kind'] + ': ' + '/'.join(c for c in cohort if c))
    return (('Quant가 전달한 인구·매출 구성 (' + '; '.join(labels) + ')을 바탕으로 이 참여 방식에 호응할지 조사. '
             '연령·성별은 각각의 분포이며 교차 고객층은 미확인. 인구 구성은 관측값이며 관심·선호는 탐색 가설입니다.') if labels else
            '고객층 자료가 없어 특정 성별·연령의 선호를 정하지 않고 참여 방식의 응용 가능성을 조사합니다.')


def context_fit(text, context):
    reasons, refs, notes = [], [], []
    preferred=primary_profile(context)
    priority=0
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
    lens_hits=0
    for lens in context.get('regional_lenses',[]):
        words=[w for term in lens.get('search_terms',[]) for w in term.split()
               if w not in ('팝업','체험','행사','투어')]
        if any(w in text for w in words):lens_hits+=1
    # Age/category word overlap is discovery metadata, not regional transfer.
    return lens_hits*3, reasons, refs, list(dict.fromkeys(notes))


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
        examples=[i for i in cases if i.get('evidence_role') != 'audience_context' and key in i['taxonomy_tags']]
        if len(examples)>=2:
            patterns.append({'pattern_id':key,'name':name,
                'description':'검색 후보에서 반복된 참여 방식 표현을 분류했습니다. 시장 추세·인기도·독립 행사 수의 근거가 아닙니다.',
                'evidence_basis':'search_metadata','verification_status':'candidate','evidence_count':len(examples),
                'example_case_ids':[i['case_id'] for i in examples],
                'example_source_ids':[sid for i in examples for sid in i['source_ids']]})
    return patterns


def run_trend_scout(request, *, context=None, detail_reader=None):
    output=search.result(request,'trend')
    output.update(patterns=[],reference_cases=[],reference_patterns=[],reference_library=[],audience_contexts=[])
    try:
        start,end,days=search.window(request)
    except (ValueError,TypeError):
        output['errors'].append({'code':'INVALID_RESEARCH_WINDOW'})
        return output
    product=(request.get('campaign') or {}).get('product') or ''
    context=deepcopy(context) if isinstance(context,dict) and context.get('request_id')==request.get('request_id') else {}
    queries=build_queries(request,context)
    output['reference_library']=library_references(request,start,end)
    output['query_context'].update(reference_date=end.isoformat(),lookback_start=start.isoformat(),lookback_days=days,
        product=product,search_queries=queries,search_plan=discovery_plan(request,context),max_queries_per_provider=MAX_QUERIES,
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
    reader_videos={}
    video_mode = os.getenv('SPOT_TREND_VIDEO_MODE', 'on')
    output['query_context']['video_mode'] = video_mode
    providers = (search.news, search.videos) if video_mode == 'on' else (search.news,)
    if video_mode != 'on':
        output['warnings'].append('YOUTUBE_LOOKUP_DISABLED' if video_mode == 'off' else 'INVALID_TREND_VIDEO_MODE')
    for provider in providers:
        provider_queries=queries
        if provider is search.videos:
            # Search videos about discovered events, not the same latest broad
            # popup results for every store. Keep the existing three-call cap.
            candidates=[i for i in by_url.values() if any(w in i['title'].lower() for w in OFFLINE_CUES)]
            candidates.sort(key=lambda i:i.get('published_at',''),reverse=True)
            candidates.sort(key=lambda i:(-context_fit(i['title']+' '+i['description'],context)[0], -sum(w in i['title'] for w in ('체험','팝업','미션','시연'))))
            event_queries=list(dict.fromkeys(video_event_query(i['title']) for i in candidates))[:MAX_QUERIES-1]
            profile=primary_profile(context)
            cohort=AGE_LABELS.get(profile.get('dominant_age'))
            audience_query=f'{cohort} 팝업' if cohort else '오프라인 체험 행사'
            provider_queries=list(dict.fromkeys(event_queries+[audience_query])) if event_queries else queries
            output['query_context']['video_search_queries']=provider_queries
        for query in provider_queries:
            for item in search.collect(output,provider,query,start,end):
                if provider is search.videos and query in event_queries:
                    terms=[w for w in query.split() if len(w)>=2 and not re.fullmatch(r'\d+(?:대|년|월|일)?',w)
                           and w not in ('팝업','체험','페스티벌','총정리','오프라인','마라톤','운영','축제','공유','개최','행사','브랜드','직접','이상','서울','부산','대구','광주','홍대')]
                    if terms and not any(w in item['title']+' '+item['description'] for w in terms):
                        continue
                if provider is search.videos and any(w in item['title'].lower() for w in OFFLINE_CUES) and not any(w in item['title'].lower() for w in ('최저가','구매링크','구매 링크','언박싱','unboxing')):
                    reader_videos[item['source_url']]={k:item[k] for k in ('source_url','source_name','source_type','published_at','collected_at','title') if k in item}
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
        # Video descriptions often contain unrelated recommendations/links.
        # Require an offline-event cue in the headline for either provider.
        cue_text=item['title']
        if not any(w in cue_text.lower() for w in OFFLINE_CUES):
            continue
        if any(w in item['title'].lower() for w in ('최저가', '구매링크', '구매 링크', '언박싱', 'unboxing')):
            continue
        mechanisms = [key for key, (_, words) in PATTERNS.items()
                      if any(relevance.contains_experience_keyword(w, text.lower(), text.lower().replace(' ', '')) for w in words)]
        score_delta,why,refs,limits=context_fit(text,context)
        # Product/geographic match never determines inclusion or priority.
        audience_context = any(w in text for w in ('참여 의사', '참여의사', '참여 의향', '설문조사', '선호도 조사')) and not any(w in item['title'] for w in ('팝업', '개막', '개최', '열린다', '연다'))
        ranked.append(dict(item,event_name=item['title'],event_category=event_category(item['title']),
            evidence_role='audience_context' if audience_context else 'experience_candidate',
            score=3+min(len(mechanisms),3)+score_delta,
            product_match_level=title_match,relevance_reasons=['전국 오프라인 체험 후보', '체험 방식 표현: ' + ', '.join(mechanisms)],
            context_fit_reasons=why,context_source_refs=refs,context_limitations=limits,
            request_relevance='same_product' if title_match=='exact' else 'adjacent_category' if category else 'cross_industry_transfer'))
    ranked.sort(key=lambda i:(-i['score'],i['source_url']))
    # Select coverage-group representatives with category breadth before the
    # provider cap, then retain additional coverage where capacity remains.
    groups = group_coverage(ranked, product)
    representatives = [g[0] for g in groups]
    priority, seen = [], set()
    ordered = [i for i in representatives if i['event_category'] != 'other'] + [i for i in representatives if i['event_category'] == 'other']
    for item in ordered:
        if item['event_category'] not in seen and item['evidence_role'] != 'audience_context':
            priority.append(item)
            seen.add(item['event_category'])
    priority.extend(i for i in representatives if i not in priority)
    priority.extend(i for i in ranked if i not in priority)
    provider_counts={}
    for item in priority:
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
            'context_match_score':context_fit(text,context)[0],
            'context_source_refs':refs,'why_relevant':why,
            'event_category':item['event_category'], 'evidence_role':item['evidence_role'],
            'audience_hypothesis':audience_hypothesis(context),
            'adaptation_hypotheses':adaptation_hypotheses(tags,product) if item['evidence_role'] != 'audience_context' else [],
            'limitations':['원문·영상·실제 행사 여부와 대상 고객은 확인하지 않았습니다.','인구 구성과 단어 겹침은 효과·취향·수요를 증명하지 않습니다.']+item['context_limitations'],
            'origin':'live_search_candidate'})
    output['reference_cases']=diversified_references(output['insights'])
    # The video player is a reader library, independent of news selection caps.
    output['reader_video_sources']=[{**s,'source_id':f'V-T-{i+1:03}'} for i,s in enumerate(list(reader_videos.values())[:10])]
    mode = os.getenv('SPOT_TREND_DETAIL_MODE', 'off')
    reader = detail_reader or (check_detail if mode == 'article' else None)
    if os.getenv('SPOT_SCOUT_MODE') == 'offline':
        reader = None
    if mode not in ('off', 'article'):
        output['warnings'].append('INVALID_TREND_DETAIL_MODE')
    enrich_references(output, context, PATTERNS, start, end, reader=reader)
    output['audience_contexts'] = deepcopy([i for i in output['insights'] if i['evidence_role'] == 'audience_context'])
    output['patterns']=build_patterns(output['insights'])
    output['reference_patterns']=build_patterns(output['reference_cases'])
    output['status']='partial' if output['insights'] else 'failed'
    output['summary']=f"전국·다업종 검색 후보 {len(output['insights'])}건 중 참고 후보 {len(output['reference_cases'])}건. 고객층 연결·매장 응용은 조사 가설이며 실제 호응은 미확인."
    output['finished_at']=search.now()
    return output
