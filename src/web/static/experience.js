'use strict';
// Presentation stays derived from returned evidence; it never synthesizes facts.
const SPOTExperience = (() => {
  const $ = id => document.getElementById(id);
  const make = (tag, text, cls, parent) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    if (parent) parent.append(el);
    return el;
  };
  let map, marker, areaMap, selection = null, searchRevision = 0;
  const field = name => document.querySelector(`[name=${name}]`);
  const message = text => { $('place-message').textContent = text; };
  const errors = {MAP_NOT_CONFIGURED:'카카오 장소 검색 설정을 확인해주세요.', PLACE_RATE_LIMIT:'검색이 많아요. 잠시 후 다시 시도해주세요.', ADDRESS_NOT_FOUND:'이 지점의 주소를 찾지 못했어요. 인근 도로나 건물을 선택해주세요.', SESSION_EXPIRED:'접속이 만료됐어요. 화면을 새로고침해주세요.'};
  async function request(url) {
    const response = await fetch(url, {signal:AbortSignal.timeout(15000)});
    const data = await response.json();
    if (!response.ok) throw new Error(errors[data.error?.code] || '장소를 조회하지 못했어요. 잠시 후 다시 시도해주세요.');
    return data.results;
  }
  function choose(place) {
    selection = place;
    field('name').value = place.name;
    for (const key of ['address','lat','lng']) field(key).value = place[key];
    $('selected-place').textContent = `${place.name} · ${place.address}`;
    message('위치 선택 완료 · 매장 이름은 원하는 이름으로 바꿀 수 있어요.');
    if (map) {
      map.setView([place.lat,place.lng],16);
      if (marker) marker.remove();
      marker = L.circleMarker([place.lat,place.lng],{radius:10,color:'#fff',weight:4,fillColor:'#2674ff',fillOpacity:1}).addTo(map);
    }
  }
  function openMap() {
    if (!map && typeof L !== 'undefined') {
      map = L.map('location-map',{zoomControl:true}).setView([36.3,127.8],7);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
        maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',
        attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
      }).on('tileerror',()=>message('지도 배경을 불러오지 못했어요. 장소 검색으로도 위치를 선택할 수 있어요.')).addTo(map);
    }
    if (map) setTimeout(()=>map.invalidateSize(),50);
  }
  async function search() {
    const query=$('place-query').value.trim();
    if(query.length<2) { message('장소 또는 주소를 두 글자 이상 입력해주세요.'); return; }
    const version=++searchRevision;
    message('카카오에서 장소와 주소를 검색하고 있어요…');
    $('place-results').replaceChildren();
    try {
      const results=await request(`/api/places/search?q=${encodeURIComponent(query)}`);
      if(version!==searchRevision)return;
      message(results.length?`${results.length}개 결과 · 조사할 매장을 선택해주세요.`:'검색 결과가 없어요. 매장명에 지역명을 붙이거나 매장 주소로 검색해주세요.');
      for(const place of results) {
        const button=make('button',undefined,'place-option',$('place-results'));button.type='button';
        make('strong',place.name,'',button);make('span',place.address,'',button);
        button.addEventListener('click',()=>{choose(place);$('place-results').replaceChildren();});
      }
    } catch(error) {if(version===searchRevision)message(error.message);}
  }
  $('place-search').addEventListener('click',search);
  $('place-query').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();search();}});
  document.querySelectorAll('[data-new]').forEach(button=>button.addEventListener('click',()=>setTimeout(openMap,0)));
  $('research-form').addEventListener('submit',event=>{
    if(!selection || field('address').value!==selection.address || Number(field('lat').value)!==selection.lat || Number(field('lng').value)!==selection.lng){
      event.preventDefault();event.stopImmediatePropagation();
      $('form-error').hidden=false;$('form-error').textContent='검색 결과에서 조사할 매장 또는 매장 주소를 먼저 선택해주세요.';
    }
  });
  function workspace(active) {
    document.body.classList.toggle('landing',!active);
    if(active&&areaMap)setTimeout(()=>areaMap.invalidateSize(),0);
  }
  const done = state => ['success','partial','completed','failed'].includes(state);
  function progress(status, stages={}) {
    workspace(true);
    document.body.classList.toggle('research-completed',status==='completed');
    const flow=[['요청 접수',status!=='connecting'],['데이터 조사',done(stages.trend)],['분석 및 통합',done(stages.merge)],['연결·차별성 검토',done(stages.semantic)],['브리프 생성',status==='completed']];
    $('research-steps').replaceChildren();
    let activeFound=false;
    flow.forEach(([name,finished],index)=>{
      const complete=status==='completed'||finished;
      const active=!complete&&!activeFound;
      if(active)activeFound=true;
      const item=make('li',undefined,complete?'done':active?'active':'',$('research-steps'));
      make('span',complete?'✓':String(index+1),'step-dot',item);make('strong',name,'',item);
      if(active)item.setAttribute('aria-current','step');
    });
    if(status!=='completed') {
      for(const [index,key] of ['quant','local','trend'].entries()) {
        const card=$('scout-cards').children[index],state=stages[key];
        if(!card)continue;
        const label=card.querySelector('.scout-state');
        if(label)label.textContent=({running:'조사 중…',success:'✓ 자료 확보',partial:'일부 자료 확보',failed:'자료 미확보',completed:'완료'})[state] || (key==='trend'?'상권·지역 결과 대기':'조사 시작 대기');
        card.classList.toggle('is-running',state==='running');
      }
      $('progress-note').textContent=stages.retry==='running'?'일시적으로 실패한 조사 항목을 다시 확인하고 있어요.':stages.semantic==='running'?'확보한 사례를 바탕으로 매장 응용의 연결성과 차별성을 검토하고 있어요.':'Quant와 Local이 먼저 조사하고, Trend가 그 결과를 받아 전국의 체험 사례를 찾습니다. 화면은 실제 실행 상태를 표시합니다.';
    }
  }
  function safeImage(value) {
    try {const url=new URL(value);if(url.protocol==='https:'&&!url.username&&!url.password&&!/^(localhost|127\.|10\.|192\.168\.|\[)/.test(url.hostname))return url.href;} catch {}
    return null;
  }
  function editorial(target,items) {
    target.classList.add('editorial-list');
    [...target.children].forEach((row,index)=>{
      if(!items[index])return;
      row.classList.add('editorial-row');
      const number=make('span',String(index+1).padStart(2,'0'),'story-number');row.prepend(number);
      const source=(items[index].sources||[]).find(s=>safeImage(s.verification?.thumbnail_url));
      if(source){
        const link=make('a',undefined,'story-photo',row);link.href=source.source_url;link.target='_blank';link.rel='noopener noreferrer';
        const image=make('img',undefined,'',link);image.src=safeImage(source.verification.thumbnail_url);image.alt='기사 대표 이미지';image.loading='lazy';image.referrerPolicy='no-referrer';
        image.addEventListener('error',()=>link.remove());
      }
    });
  }
  function category(source) {
    const hint=[source.source_type,source.type,source.source_name,source.title].filter(Boolean).join(' ');
    if(/report|보고서|연구보고/i.test(hint)||/\.pdf(?:\?|$)/i.test(source.source_url||''))return '보고서';
    if(/public|government|공공|소상공인|통계/i.test(hint)||/\.go\.kr(?:\/|$)/i.test(source.source_url||''))return '공공데이터';
    if(/news|뉴스|신문|일보|기사/i.test(hint)||source.verification?.method==='article_text_check')return '뉴스';
    return '기타';
  }
  function overviewMap(request){
    const host=$('area-map'),caption=$('area-map-caption');
    if(areaMap){areaMap.remove();areaMap=null;}
    host.replaceChildren();
    const {lat,lng}=request?.store||{},radius=request?.research?.radius_m;
    const numeric=value=>typeof value==='number'&&Number.isFinite(value);
    if(typeof L==='undefined'||!numeric(lat)||!numeric(lng)||Math.abs(lat)>90||Math.abs(lng)>180){
      make('div','⌖','area-map-empty-icon',host);make('p',request?.store?.address||'조사 위치 좌표 미확보','area-map-empty',host);caption.textContent='좌표가 확보된 요청에 조사 위치와 반경을 표시합니다.';return;
    }
    areaMap=L.map(host,{zoomControl:true,scrollWheelZoom:false}).setView([lat,lng],15);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'}).on('tileerror',()=>{caption.textContent='지도 배경을 불러오지 못했어요. 주소와 요청 반경은 아래 표시를 확인해주세요. '+(request.store.address||'');}).addTo(areaMap);
    if(numeric(radius)&&radius>0){const circle=L.circle([lat,lng],{radius,color:'#3868f5',weight:2,dashArray:'6 6',fillColor:'#3868f5',fillOpacity:0.12}).addTo(areaMap);areaMap.fitBounds(circle.getBounds(),{padding:[20,20]});}
    const pin=L.circleMarker([lat,lng],{radius:9,color:'#fff',weight:3,fillColor:'#3868f5',fillOpacity:1}).addTo(areaMap);
    const label=make('strong',request.store.name||'조사 위치');pin.bindTooltip(label,{permanent:true,direction:'top',offset:[0,-10]});
    caption.textContent=`요청 위치 · ${numeric(radius)?'조사 반경 '+radius.toLocaleString('ko-KR')+'m':'반경 미확인'} / 공공자료의 집계 범위는 개별 출처에서 확인하세요.`;
    setTimeout(()=>areaMap?.invalidateSize(),0);
  }
  function storyPreview(target,items,module,evidence){
    target.replaceChildren();
    if(!items.length){make('p',module==='local'?'지역 변화 근거를 확보하지 못했어요.':'전국 참고 자료를 확보하지 못했어요.','empty',target);return;}
    items.slice(0,2).forEach((card,index)=>{
      const article=make('article',undefined,'overview-story '+module+'-preview',target);
      const imageSource=(card.sources||[]).find(s=>safeImage(s.verification?.thumbnail_url));
      if(imageSource){const frame=make('div',undefined,'preview-image',article),image=make('img',undefined,'',frame);image.src=safeImage(imageSource.verification.thumbnail_url);image.alt='출처에서 제공한 대표 이미지';image.loading='lazy';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>frame.remove());}
      else if(module==='trend'){const cover=make('div',undefined,'preview-cover cover-'+index,article);make('span',card.type==='reference_case'?'EXPERIENCE CASE':'EXPERIENCE PATTERN','',cover);make('strong',card.event_category||card.pattern_type||'전국 체험 참고','',cover);}
      const body=make('div',undefined,'preview-body',article);
      if(module==='local')make('span',String(index+1).padStart(2,'0'),'preview-number',body);
      make('h4',card.title||card.event_name||card.name||'체험 참고 자료','',body);
      make('p',card.why_it_matters||card.statement||card.evidence||card.observation||card.description||card.summary||'근거와 해석 범위를 확인하세요.','',body);
      if(module==='trend'){const adaptation=card.adaptation_hypotheses?.[0];if(adaptation)make('p',typeof adaptation==='string'?adaptation:adaptation.statement||'','preview-adaptation',body);}
      const footer=make('div',undefined,'preview-footer',body);make('span',module==='local'?(card.published_at||card.sources?.[0]?.published_at||'게시일 미확인'):'매장 연결은 조사 가설','',footer);
      const button=make('button','근거 보기 ↗','text-button',footer);button.type='button';button.addEventListener('click',()=>evidence(card,module));
    });
  }
  function overview(quant,local,trend,request,evidence){
    const metrics=$('overview-metrics'),tags=$('area-tags');metrics.replaceChildren();tags.replaceChildren();
    const number=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
    const metric=ref=>quant.find(c=>c.metric_refs?.includes(ref)&&c.sources?.length);
    const population=metric('daily_avg_floating_population'),time=metric('peak_floating_time_band');
    const age=typeof SPOTQuantCharts!=='undefined'?SPOTQuantCharts.chartCard(quant,'floating_population','age'):null;
    const ageRows=typeof SPOTQuantCharts!=='undefined'?SPOTQuantCharts.rows(age,'age','floating_population').filter(r=>r.value!==null):[];
    const max=Math.max(0,...ageRows.map(r=>r.value)),top=ageRows.filter(r=>r.value===max),ageLabel=top.map(r=>r.label).join(' · ');
    const ageComplete=ageRows.length>0&&ageRows.length===SPOTQuantCharts.rows(age,'age','floating_population').length;
    if(ageRows.length)$('area-title').textContent=ageRows.length===SPOTQuantCharts.rows(age,'age','floating_population').length?`${ageLabel} 방문 비중이 가장 높은 지역`:`확보된 연령 중 ${ageLabel} ${max}%`;
    const cases=trend.filter(c=>c.type==='reference_case'),patterns=trend.filter(c=>c.type==='pattern');
    const chosen=cases.length?cases:patterns.length?patterns:trend;
    const definitions=[['일평균 유동인구',number(population?.value)?population.value.toLocaleString('ko-KR')+'명':'미확보',population,'quant','◫'],[ageRows.length&&!ageComplete?'확보 연령 중 최다':'주요 연령대',ageRows.length?`${ageLabel} · ${max}%`:'미확보',age,'quant','◉'],['주요 유동 시간',time?.value??'미확보',time,'quant','◷'],[cases.length?'전국 참고 사례':'체험 패턴',String(chosen.length)+'건',chosen[0],'trend','↗']];
    definitions.forEach(([title,value,card,module,icon],i)=>{const tile=make('article',undefined,'overview-metric metric-tone-'+i,metrics);make('span',icon,'metric-icon',tile);const text=make('div',undefined,'',tile);make('p',title,'',text);make('strong',String(value),'',text);if(card){const button=make('button','근거 ↗','text-button',text);button.type='button';button.addEventListener('click',()=>evidence(card,module));}});
    for(const [i,text] of [ageRows.length?ageLabel+' 방문 비중 '+max+'%':null,local.length?'지역 변화 '+local.length+'건':null,chosen.length?'전국 체험 '+chosen.length+'건':null].entries())if(text)make('span',text,'tag-tone-'+i,tags);
    if(typeof SPOTQuantCharts!=='undefined')SPOTQuantCharts.preview(document,$('overview-population'),quant,evidence);
    else make('p','고객 분포를 확인할 자료가 미확보됐어요.','empty',$('overview-population'));
    storyPreview($('overview-local'),local,'local',evidence);storyPreview($('overview-trend'),chosen,'trend',evidence);overviewMap(request);
  }
  function library(target,groups,sourceRow) {
    target.replaceChildren();const sources=[],seen=new Set();
    for(const [items,module] of groups)for(const card of items)for(const source of card.sources||[]){
      const id=source.source_url||`${module}:${source.source_id}`;if(seen.has(id))continue;seen.add(id);sources.push([source,module]);
    }
    const tabs=make('div',undefined,'source-tabs',target);tabs.setAttribute('aria-label','출처 분류');
    const list=make('div',undefined,'source-list',target);
    function select(label) {
      [...tabs.children].forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.category===label)));
      list.replaceChildren();const filtered=sources.filter(([s])=>label==='전체'||category(s)===label);
      for(const [source,module] of filtered)sourceRow(source,list,module);
      if(!filtered.length)make('p','이 분류에 연결된 출처가 없습니다.','empty',list);
    }
    for(const label of ['전체','뉴스','공공데이터','보고서','기타']){
      const count=sources.filter(([s])=>label==='전체'||category(s)===label).length;
      const button=make('button',`${label} (${count})`,'',tabs);button.type='button';button.dataset.category=label;button.addEventListener('click',()=>select(label));
    }
    select('전체');
  }
  function display(brief,request,sourceRow,evidence) {
    const signals=brief.unique_local_signals||[],quant=signals.filter(c=>c.module==='quant'),local=brief.local_changes||[],context=signals.filter(c=>c.module!=='quant'),trend=brief.trend_patterns||[];
    const quantFailure=(brief.needs_manual_check||[]).find(text=>typeof text==='string'&&text.startsWith('quant: '));
    if(!quant.length&&quantFailure){
      $('quant-cards').replaceChildren();
      make('p',quantFailure.slice(7),'empty',$('quant-cards'));
    }
    const population=quant.filter(c=>c.population_kind||c.shares||/성별|연령|시간대/.test(c.title||''));
    const trendHighlights=trend.filter(c=>c.type==='reference_case');
    const highlights=[...population.slice(0,1).map(c=>[c,'quant']),...local.slice(0,1).map(c=>[c,'local']),...(trendHighlights.length?trendHighlights:trend).slice(0,1).map(c=>[c,'trend'])];
    if(!highlights.length)highlights.push(...quant.slice(0,2).map(c=>[c,'quant']));
    const sentence=card=>String(card.statement||card.evidence||card.observation||card.title||card.event_name||card.name||'').slice(0,180);
    const parts=[];
    if(population[0])parts.push(`공공 상권 자료에서 ${sentence(population[0])}${/[.!?。]$/.test(sentence(population[0]))?'':'입니다.'}`);
    if(population[1])parts.push(`${sentence(population[1])}${/[.!?。]$/.test(sentence(population[1]))?'':'입니다.'}`);
    if(local[0])parts.push(`지역 자료에서는 ‘${local[0].title||sentence(local[0])}’ 내용을 다룹니다.`);
    else if(quant.length)parts.push('지역의 직접적인 변화는 추가 확인이 필요합니다.');
    if(!parts.length&&quant[0])parts.push(sentence(quant[0]));
    if(trend.some(c=>c.type==='reference_case'))parts.push('전국 체험 사례의 참여 방식을 매장 캠페인에 접목할 수 있을지 검토합니다.');
    $('area-summary').textContent=parts.join(' ')||'이 지역을 요약할 근거가 아직 충분하지 않습니다.';
    $('key-insights').replaceChildren();
    highlights.forEach(([card,module],index)=>{
      const button=make('button',undefined,'key-insight',$('key-insights'));button.type='button';
      const title=card.title||card.event_name||card.name||sentence(card);
      make('span',String(index+1).padStart(2,'0'),'',button);make('strong',title+(card.value!==undefined?` · ${card.value}${card.unit||''}`:''),'',button);
      make('small',module==='trend'?(card.type==='reference_case'?'전국 참고 사례':'체험 패턴'):module==='quant'?'공공 관측값':'지역 자료','',button);
      const detail=card.why_it_matters||card.statement||card.evidence||card.observation||card.description||card.summary;
      if(detail)make('p',detail,'key-insight-detail',button);
      button.addEventListener('click',()=>evidence(card,module));
    });
    if(!highlights.length)make('p','핵심 인사이트를 제시할 근거가 미확보됐어요.','muted',$('key-insights'));
    overview(quant,local,trend,request,evidence);
    editorial($('local-cards'),local);editorial($('context-cards'),context);
    library($('local-sources'),[[local.concat(context),'local']],sourceRow);
    library($('source-list'),[[quant,'quant'],[local.concat(context),'local'],[trend,'trend'],...trend.flatMap(c=>Object.entries(c.context_sources||{}).map(([module,sources])=>[[{sources}],module]))],sourceRow);
  }
  return {workspace,progress,display};
})();
