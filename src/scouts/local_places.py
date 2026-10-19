"""Bounded place context. Search coverage is not a facility census or footfall."""
import math
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from src.scouts import search_runtime as search
from src.scouts.local_evidence import fetch_article, ArticleParser

CATEGORIES = [('SW8','교통'),('SC4','교육'),('CT1','문화'),('AT4','관광'),('PO3','공공시설'),('BK9','금융'),('MT1','생활 쇼핑')]
KEYWORDS = [('아파트','주거'),('오피스','업무'),('시장','시장')]

def distance(lat,lng,y,x):
    a,b=map(math.radians,(lat,y));dl=math.radians(x-lng);da=b-a
    v=math.sin(da/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
    return round(6371000*2*math.asin(min(1,math.sqrt(v))))

def collect_places(request, output):
    store=request.get('store') or {}
    try:
        lat,lng=float(store['lat']),float(store['lng'])
        radius=int((request.get('research') or {}).get('radius_m',1000))
        if not (32<=lat<=39.5 and 124<=lng<=132 and 0<radius<=20000):return
        search.credentials()
        key=os.getenv('KAKAO_REST_API_KEY','').strip()
        if not key:raise search.SearchError('MISSING_KAKAO_REST_API_KEY')
    except (KeyError,TypeError,ValueError):
        output['warnings'].append('LOCAL_PLACES_REQUIRE_COORDINATES');return
    except search.SearchError as exc:
        output['warnings'].append('LOCAL_PLACES_'+exc.code);return
    tasks=[('category',code,label) for code,label in CATEGORIES]+[('keyword',word,label) for word,label in KEYWORDS]
    def lookup(task):
        kind,term,label=task
        params={'x':lng,'y':lat,'radius':radius,'size':5,'sort':'distance','page':1,
                'category_group_code' if kind=='category' else 'query':term}
        try:
            data=search.get_json('https://dapi.kakao.com/v2/local/search/'+kind+'.json',params,{'Authorization':'KakaoAK '+key})
            rows=data.get('documents')
            if not isinstance(rows,list):raise search.SearchError('INVALID_PROVIDER_RESPONSE')
            return label,rows,None
        except search.SearchError as exc:return label,[],exc.code
    seen=set();places=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for label,rows,error in pool.map(lookup,tasks):
            if error:output['warnings'].append('LOCAL_PLACES_'+error)
            accepted=0
            for row in rows:
                try:
                    name=search.clean(row['place_name']);pid=str(row['id']);y,x=float(row['y']),float(row['x'])
                    category=str(row.get('category_name') or '')
                    if label=='주거' and not any(w in category for w in ('아파트','주거시설','오피스텔')):continue
                    if label=='업무' and (not any(w in category for w in ('빌딩','사무실','공유오피스')) or '오피스텔' in category):continue
                    if label=='시장' and '시장' not in category:continue
                    if not name or not math.isfinite(y+x):continue
                    meters=distance(lat,lng,y,x)
                    url=str(row['place_url']);parts=urlsplit(url)
                    if parts.hostname!='place.map.kakao.com' or parts.scheme not in ('http','https') or parts.username or parts.password:continue
                    if meters>radius or pid in seen:continue
                except (KeyError,ValueError,TypeError):continue
                seen.add(pid);accepted+=1
                sid=f'S-L-P-{len(places)+1:03}'
                detail={'name':name,'category':label,'address':search.clean(row.get('road_address_name') or row.get('address_name')),
                        'lat':y,'lng':x,'distance_m':meters,'zone':'가까운 주변' if meters<=500 else '넓은 주변'}
                evidence=f"{name} · {label} · 매장에서 직선거리 약 {meters}m · {detail['address']}"
                source={'source_id':sid,'source_name':'Kakao Local 장소 정보','source_type':'map','source_url':url,
                        'title':name,'published_at':None,'collected_at':search.now()}
                output['sources'].append(source)
                card={'insight_id':sid.replace('S-',''),'type':'local_place','title':name,'evidence':evidence,
                      'evidence_role':'background','evidence_basis':'place_api','verification_status':'provider_observation',
                      'change_state':'not_applicable','source_ids':[sid],'published_at':None,'place':detail,
                      'context_note':'검색된 장소의 위치·분류입니다. 전체 시설 수, 실제 이동 동선이나 방문 목적을 측정한 결과가 아닙니다.'}
                output['insights'].append(card);places.append(card)
                if accepted==3:break
    output['query_context']['place_search']={'radius_m':radius,'near_radius_m':min(500,radius),'categories':[t[2] for t in tasks],
        'returned_places':len(places),'coverage':'bounded_nearest_results','distance_basis':'straight_line'}
    official_context(store,places,output)

def official_context(store,places,output):
    """Read at most two matched government pages; never trust search snippets alone."""
    client,secret=os.getenv('NAVER_CLIENT_ID',''),os.getenv('NAVER_CLIENT_SECRET','')
    if not client or not secret:return
    selected=[p for p in places if p['place']['category'] in ('문화','관광','공공시설')][:2]
    city=(store.get('address') or '').split(' ')[0]
    seen=set()
    for place in selected:
        name=place['place']['name'];query=f'{city} {name} 소개 site:go.kr'
        headers={'X-Naver-Client-Id':client,'X-Naver-Client-Secret':secret}
        endpoint='https://openapi.naver.com/v1/search/webkr.json'
        try:
            if os.getenv('NAVER_SEARCH_PROVIDER')=='hub':
                endpoint='https://naverapihub.apigw.ntruss.com/search/v1/webkr';headers={'X-NCP-APIGW-API-KEY-ID':client,'X-NCP-APIGW-API-KEY':secret}
            try:
                data=search.get_json(endpoint,{'query':query,'display':3},headers)
            except search.SearchError as exc:
                if os.getenv('NAVER_SEARCH_PROVIDER','auto')!='auto' or exc.status not in (401,403):raise
                data=search.get_json('https://naverapihub.apigw.ntruss.com/search/v1/webkr',{'query':query,'display':3},
                    {'X-NCP-APIGW-API-KEY-ID':client,'X-NCP-APIGW-API-KEY':secret})
            for item in data.get('items',[])[:3]:
                url=item.get('link','');host=urlsplit(url).hostname or ''
                if not host.endswith('.go.kr') or url in seen:continue
                html,resolved=fetch_article(url)
                if not (urlsplit(resolved).hostname or '').endswith('.go.kr'):continue
                parser=ArticleParser();parser.feed(html)
                blocks=parser.document()[0]
                match=next((b for b in blocks if search.normalized(name) in search.normalized(b) and len(b)>40),None)
                if not match:continue
                seen.add(url);sid=f'S-L-O-{len(seen):03}'
                output['sources'].append({'source_id':sid,'source_name':host,'source_type':'government','source_url':resolved,
                    'title':search.clean(item.get('title')),'published_at':None,'collected_at':search.now()})
                output['insights'].append({'insight_id':sid.replace('S-',''),'type':'local_official_context','title':name+' · 공식 안내',
                    'evidence':search.clean(match)[:450],'evidence_role':'background','evidence_basis':'official_page',
                    'verification_status':'context_corroborated','change_state':'not_applicable','published_at':None,'source_ids':[sid],
                    'context_note':'공식 페이지에 기재된 시설 설명입니다. 현재 운영시간·방문량이나 매장 영향은 별도입니다.'})
                break
        except search.SearchError as exc:
            output['warnings'].append('LOCAL_OFFICIAL_'+exc.code+(f'_{exc.status}' if exc.status else ''))
        except (ValueError,TypeError,KeyError):
            output['warnings'].append('LOCAL_OFFICIAL_INVALID_RESPONSE')
