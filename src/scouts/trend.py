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
}
OFFLINE_CUES = ("팝업", "체험존", "체험 공간", "체험공간", "오프라인 행사", "전시회", "전시관", "행사장", "체험관")
AGE_LABELS = {"under_10":"10세 미만", "teens":"10대", "20s":"20대", "30s":"30대", "40s":"40대", "50s":"50대", "60_plus":"60대"}
MAX_QUERIES = 3


def product_alias(product):
    alias = product
    for old,new in (("galaxy","갤럭시"),("fold","폴드"),("flip","플립"),("iphone","아이폰")):
        alias = alias.lower().replace(old,new)
    return alias


def build_queries(request, context):
    product = request['campaign']['product']
    alias = product_alias(product)
    queries = [alias + ' 팝업 체험']
    if any(w in product.lower() for w in ('galaxy','iphone','갤럭시','아이폰','스마트폰')):
        queries.append('스마트폰 팝업 체험')
    # An age query is exploratory, never proof of the audience of an event.
    age = next((s.get('dominant_age') for s in context.get('population_signals',[]) if s.get('population_kind')=='floating_population'),None)
    if age in AGE_LABELS:
        queries.append(alias + ' 체험 ' + AGE_LABELS[age])
    else:
        precision = relevance.build_search_queries(request)
        if precision:
            queries.append(precision[0])
    return list(dict.fromkeys(queries))[:MAX_QUERIES]


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
        scope='제품·인접 카테고리 후보; 요청 조사 맥락을 보조적으로 대조',
        upstream_context=context, relevance_mode='PR14_heuristics_with_bounded_context_signals')
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
        scored=relevance.score_candidate_relevance(dict(item,channel_title=item.get('source_name','')),request)
        title_match,_=relevance.find_product_match(item['title'].lower(),item['title'].lower().replace(' ',''),product)
        category=phone and any(w in item['title'].lower() for w in ('스마트폰','갤럭시','아이폰','galaxy','iphone'))
        cue_text=item['title'] if item['source_type']=='news' else text
        if not any(w in cue_text.lower() for w in OFFLINE_CUES):
            continue
        if item['source_type']=='news' and title_match=='none' and not category:
            continue
        adjacent=category and not scored['review_keyword_hits'] and not scored['commerce_keyword_hits']
        if not scored['is_experiential_candidate'] and not adjacent:
            continue
        score_delta,why,refs,limits=context_fit(text,context)
        ranked.append(dict(item,score=scored['relevance_score']+score_delta,
            product_match_level=scored['product_match_level'],relevance_reasons=scored['relevance_reasons'],
            context_fit_reasons=why,context_source_refs=refs,context_limitations=limits,
            request_relevance='same_product' if scored['exact_product_match'] else 'adjacent_category'))
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
        output['sources'].append({k:item[k] for k in ('source_url','source_name','source_type','published_at','collected_at','date_basis') if k in item} | {'source_id':sid,'verification':{'method':'search_metadata','event_verified':False}})
        why=['요청 제품이 직접 언급된 체험 후보입니다.' if item['request_relevance']=='same_product' else '요청 제품과 인접한 카테고리의 체험 구조를 비교할 후보입니다.']+item['context_fit_reasons']
        output['insights'].append({'case_id':cid,'type':'experiential_marketing_candidate','event_name':item['title'],
            'observation':item['description'],'published_at':item['published_at'],'brand':None,'location':None,
            'source_ids':[sid],'taxonomy_tags':tags,'verification_status':'candidate',
            'request_relevance':item['request_relevance'],'product_match_level':item['product_match_level'],
            'reference_priority_score':item['score'],'fit_signals':item['relevance_reasons'],
            'context_source_refs':item['context_source_refs'],'why_relevant':why,
            'limitations':['원문·영상·실제 행사 여부와 대상 고객은 확인하지 않았습니다.','인구 구성과 단어 겹침은 효과·취향·수요를 증명하지 않습니다.']+item['context_limitations'],
            'origin':'live_search_candidate'})
    output['reference_cases']=deepcopy(output['insights'][:5])
    output['patterns']=build_patterns(output['insights'])
    output['reference_patterns']=build_patterns(output['reference_cases'])
    output['status']='partial' if output['insights'] else 'failed'
    output['summary']=f"실제 검색 후보 {len(output['insights'])}건 중 요청 맥락을 대조한 참고 후보 {len(output['reference_cases'])}건. 실제 행사·고객 적합성 검토 필요."
    output['finished_at']=search.now()
    return output
