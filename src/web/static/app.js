'use strict';
// A bounded subset of Markdown rendered only through DOM text nodes.
function renderBrief(doc, target, markdown) {
  target.replaceChildren();
  let section = target, list = null;
  const lines = markdown.split('\n');
  function inline(parent, text) {
    const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
    let start = 0;
    for (const match of text.matchAll(pattern)) {
      parent.append(doc.createTextNode(text.slice(start, match.index)));
      try {
        const url = new URL(match[2]);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error();
        const a = doc.createElement('a');
        a.href = url.href; a.textContent = match[1]; a.target = '_blank'; a.rel = 'noopener noreferrer';
        parent.append(a);
      } catch { parent.append(doc.createTextNode(match[0])); }
      start = match.index + match[0].length;
    }
    parent.append(doc.createTextNode(text.slice(start)));
  }
  function element(tag, text, parent = section) {
    const node = doc.createElement(tag); inline(node, text); parent.append(node); return node;
  }
  function cells(line) { return line.trim().replace(/^\||\|$/g, '').split('|').map(value => value.trim()); }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) { list = null; continue; }
    // Request identifiers remain in the download, not in the reader view.
    if (line.startsWith('# ') || line.startsWith('- 요청:')) continue;
    if (line.startsWith('## ')) {
      list = null;
      const group = doc.createElement('details');
      group.open = /상권·인구|성별·연령|Critic/.test(line);
      element('summary', line.slice(3), group);
      section = doc.createElement('div'); section.className = 'brief-section'; group.append(section); target.append(group);
    } else if (line.startsWith('### ')) {
      list = null; element('h3', line.slice(4));
    } else if (line.startsWith('|') && /^\|?[\s:|\-]+\|?$/.test(lines[i + 1] || '')) {
      list = null;
      const wrapper = doc.createElement('div'); wrapper.className = 'table-scroll';
      const table = doc.createElement('table'); wrapper.append(table); section.append(wrapper);
      const head = doc.createElement('thead'), headRow = doc.createElement('tr'); head.append(headRow); table.append(head);
      for (const cell of cells(line)) element('th', cell, headRow);
      const body = doc.createElement('tbody'); table.append(body); i++;
      while ((lines[i + 1] || '').trim().startsWith('|')) {
        const row = doc.createElement('tr'); body.append(row);
        for (const cell of cells(lines[++i])) element('td', cell, row);
      }
    } else if (line.startsWith('- ')) {
      if (!list) { list = doc.createElement('ul'); section.append(list); }
      element('li', line.slice(2), list);
    } else {
      list = null; element('p', line);
    }
  }
}
if (typeof module !== 'undefined') module.exports = {renderBrief};

if (typeof document !== 'undefined') {
const $ = id => document.getElementById(id);
const labels={overview:'Overview',quant:'상권 · 고객 구성',local:'지역 변화',trend:'체험 트렌드',brief:'Research Brief',sources:'Sources',history:'Research History'};
const modules={quant:{name:'상권 · 고객 구성',icon:'◫',description:'소상공인365 상권·인구 관측값'},local:{name:'지역 변화',icon:'⌖',description:'요청 지역의 변화와 생활권 맥락'},trend:{name:'체험 트렌드',icon:'↗',description:'전국 · 다업종 참여 방식과 응용 가설'}};
let pending=null,activeJob=null,timer=null,markdown='',polls=0,current='overview',lastRequest=null,history=[];
let cached=null;
const errors={CONNECTION_AUTH:'서버 연결 인증을 확인해야 해요.',CONNECTION_UNAVAILABLE:'조사 서버에 연결할 수 없어요. PC와 개발 터널이 켜져 있는지 확인해주세요.',SESSION_EXPIRED:'접속 시간이 만료됐어요. 페이지를 새로 열어주세요.',INVALID_REQUEST:'입력 항목과 좌표를 확인해주세요.',JOB_NOT_FOUND:'작업이 만료됐거나 이 화면에서 접수한 작업이 아니에요.',REQUEST_CONFLICT:'같은 요청 번호에 다른 입력이 들어왔어요.',BUSY:'조사 대기열이 가득 찼어요. 잠시 뒤 같은 요청을 다시 연결해주세요.',SESSION_JOB_LIMIT:'이 접속에서 조사 4건을 접수했어요. 진행 중인 결과를 먼저 확인해주세요.'};
function node(tag,text,className,parent){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;if(parent)parent.append(el);return el;}
function empty(target,text='완료된 조사 자료가 아직 없어요. Overview에서 작업 상태를 확인해주세요.'){target.replaceChildren();node('p',text,'empty',target);}
function notice(text,error=false){$('notice').hidden=false;$('notice').textContent=text;$('notice').className='notice'+(error?' error':'');}
async function api(path,options){let response;try{response=await fetch(path,{...options,signal:AbortSignal.timeout(25000)});}catch{throw new Error('CONNECTION_UNAVAILABLE');}let data;try{data=await response.json();}catch{throw new Error('CONNECTION_UNAVAILABLE');}if(!response.ok)throw new Error(data.error?.code||'CONNECTION_UNAVAILABLE');return data;}
function save(){sessionStorage.setItem('spot-work',JSON.stringify({pending,activeJob,lastRequest,history}));}
function heading(){const request=lastRequest;const store=request?.store?.name||cached?.result?.research_brief?.overview?.area_summary?.split(':')[0];const product=request?.campaign?.product;$('context-label').textContent=store?`${store}${product?' × '+product:''}`:activeJob?'CURRENT RESEARCH':'EXPLORE YOUR NEXT SPOT';$('page-title').textContent=current==='overview'?(store|| (activeJob?'지역 리서치 워크스페이스':'어디에서 캠페인을 시작할까요?')):labels[current];$('page-description').textContent=request?.store?.address||'장소와 캠페인에서 시작해, 지역의 근거와 체험의 연결점을 발견하세요.';}
function show(view){if(!labels[view])return;if(typeof SPOTExperience!=='undefined')SPOTExperience.workspace(view!=='overview'||Boolean(activeJob||pending));current=view;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${view}`);document.querySelectorAll('.nav-item').forEach(el=>{if(el.dataset.view===view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});$('current-view').textContent=labels[view];heading();if(view==='history')renderHistory();}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>show(button.dataset.view)));
document.querySelectorAll('[data-new]').forEach(button=>button.addEventListener('click',()=>{$('form-error').hidden=true;$('request-dialog').showModal();}));
$('close-request').addEventListener('click',()=>$('request-dialog').close());$('close-evidence').addEventListener('click',()=>$('evidence-dialog').close());
function sourceRow(source,target,module){const row=node('div',undefined,'source-row',target);let url;try{url=new URL(source.source_url);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)url=null;}catch{url=null;}if(url){const a=node('a',source.title||source.source_name||url.hostname,'',row);a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';}else node('strong',source.source_name||'출처 주소 미확보','',row);node('p',`${module?module.toUpperCase()+' · ':''}${source.source_id||''} · 게시일 ${source.published_at||'미확인'} · 수집일 ${source.collected_at||'미확인'}`,'',row);}
function evidence(card,module){$('evidence-title').textContent=card.title||card.event_name||card.name||'조사 신호';$('evidence-statement').textContent=card.statement||card.evidence||card.observation||card.description||'';$('evidence-meta').replaceChildren();const context=[`Used by · ${module.toUpperCase()} Scout`,card.scope&&`해석 범위 · ${card.scope}`,`자료 기준 · ${card.reference_period||'미확인'}`,card.type==='reference_case'?'연결 수준 · 체험 참고 사례 / 매장 응용은 조사 가설':'자료 수준 · 제공 관측값·보도 맥락을 확인하세요.'];for(const text of context.filter(Boolean))node('p',text,'',$('evidence-meta'));$('evidence-sources').replaceChildren();const sources=card.sources||[];if(!sources.length)empty($('evidence-sources'),'연결된 출처가 없습니다.');for(const source of sources)sourceRow(source,$('evidence-sources'),module);for(const [key,items] of Object.entries(card.context_sources||{}))for(const source of items)sourceRow(source,$('evidence-sources'),key);$('evidence-dialog').showModal();}
function cards(target,items,module){target.replaceChildren();if(!items.length){empty(target,'이번 조사에서 이 항목에 사용할 수 있는 근거를 확보하지 못했어요.');return;}for(const card of items){const box=node('article',undefined,'signal-card',target);node('p',module.toUpperCase()+' SIGNAL','eyebrow',box);node('h3',card.title||card.event_name||card.name||'조사 신호','',box);if(card.value!==undefined)node('p',`${typeof card.value==='number'?card.value.toLocaleString('ko-KR'):card.value}${card.unit||''}`,'value-line',box);node('p',card.statement||card.evidence||card.observation||card.description||card.summary||'근거와 해석 범위를 함께 확인하세요.','',box);const adaptation=card.adaptation_hypotheses;if(Array.isArray(adaptation)&&adaptation[0])node('p',typeof adaptation[0]==='string'?adaptation[0]:adaptation[0].statement||'','',box);const footer=node('div',undefined,'card-footer',box);node('span',`${(card.sources||[]).length}개 연결 근거`,'',footer);const button=node('button','근거 보기 ↗','evidence-button',footer);button.type='button';button.addEventListener('click',()=>evidence(card,module));}}
function progress(status,moduleStatus={},stages={}){$('welcome').hidden=true;$('research-workspace').hidden=false;$('overview-content').hidden=status!=='completed';$('progress-title').textContent=status==='completed'?'Research complete':'Researching this SPoT';$('job-state').textContent=({queued:'접수 · 대기',running:'조사 진행 중',completed:'브리프 생성 완료',failed:'실행 실패',connecting:'연결 중'})[status]||'상태 확인 중';$('scout-cards').replaceChildren();for(const [key,info] of Object.entries(modules)){const state=moduleStatus[key];const card=node('article',undefined,'scout-card',$('scout-cards'));node('div',info.icon,'scout-icon',card);node('span',state?({success:'✓ 자료 확보',partial:'일부 자료 확보',failed:'자료 미확보'}[state]||'상태 미확인'):(status==='failed'?'상태 미확인':'완료 결과 대기'),'scout-state '+(state||''),card);node('div',key.toUpperCase()+' SCOUT','scout-label',card);node('h3',info.name,'',card);node('p',info.description,'',card);}$('progress-note').textContent=status==='completed'?'확보한 자료와 조사 가설을 구분해 확인하세요. 일부 자료 미확보가 있어도 브리프는 보존됩니다.':'상권·지역 조사 → 체험 트렌드 탐색 → 연결·차별성 검토 순서로 조사합니다. 항목별 자료와 발견한 신호는 조사가 완료되면 표시합니다.';if(typeof SPOTExperience!=='undefined')SPOTExperience.progress(status,stages);}
function display(data){cached=data;const result=data.result||{},brief=result.research_brief||{},review=brief.research_review||{};markdown=result.research_brief_markdown||'조사 결과 본문이 없습니다.';progress('completed',result.module_status);$('area-title').textContent=lastRequest?.store?.name||'조사 지역의 근거 요약';$('area-summary').textContent=brief.overview?.area_summary||'지역 요약이 없습니다.';$('customer-signal').textContent=brief.overview?.primary_customer_signal||'인구 신호를 요약할 자료가 미확보됐어요.';$('source-count').textContent=`${brief.source_count||0}개 고유 출처`;$('why-now').textContent=brief.why_here_now||'판단할 근거가 미확보됐어요.';$('quality').textContent=(result.mode==='offline'?'외부 호출 없는 연결 확인 결과 · ':'')+(review.performed?'고객 연결·차별성 검토 포함':'고객 연결·차별성 검토 미완료 / 꺼짐')+` · ${brief.source_count||0}개 출처 연결. 확보한 조사 자료를 보존하며 사실·고객 호응·행사 효과의 최종 인증을 뜻하지 않습니다.`;
const signals=brief.unique_local_signals||[],quant=signals.filter(card=>card.module==='quant'),local=brief.local_changes||[],context=signals.filter(card=>card.module!=='quant'),trend=brief.trend_patterns||[];cards($('quant-cards'),quant,'quant');cards($('local-cards'),local,'local');cards($('context-cards'),context,'local');cards($('trend-cards'),trend,'trend');$('signal-cards').replaceChildren();const featured=[...quant.slice(0,2).map(card=>[card,'quant']),...local.slice(0,2).map(card=>[card,'local']),...trend.filter(card=>card.type==='reference_case').slice(0,2).map(card=>[card,'trend'])];if(!featured.length)empty($('signal-cards'));for(const [card,module] of featured){const staging=document.createElement('div');cards(staging,[card],module);$('signal-cards').append(...staging.children);}renderBrief(document,$('brief'),markdown);for(const title of $('brief').querySelectorAll('summary'))if(title.textContent.startsWith('Critic:'))title.textContent='고객 연결·차별성 검토';$('download').disabled=false;$('source-list').replaceChildren();const seen=new Set();for(const [items,module] of [[quant,'quant'],[local.concat(context),'local'],[trend,'trend']])for(const card of items){for(const source of card.sources||[]){const id=`${module}:${source.source_id}:${source.source_url}`;if(!seen.has(id)){seen.add(id);sourceRow(source,$('source-list'),module);}}for(const [key,items] of Object.entries(card.context_sources||{}))for(const source of items){const id=`${key}:${source.source_id}:${source.source_url}`;if(!seen.has(id)){seen.add(id);sourceRow(source,$('source-list'),key);}}}if(!seen.size)empty($('source-list'),'이용 가능한 출처가 없습니다.');if(typeof SPOTExperience!=='undefined')SPOTExperience.display(brief,lastRequest,sourceRow,evidence);heading();}
function remember(status){const entry=history.find(item=>item.job_id===activeJob);if(entry)entry.status=status;else history.unshift({job_id:activeJob,status,request:lastRequest,created_at:new Date().toISOString()});history=history.slice(0,4);save();}
function renderHistory(){$('history-list').replaceChildren();if(!history.length){empty($('history-list'),'이 탭에서 접수한 리서치가 아직 없습니다.');return;}for(const item of history){const row=node('article',undefined,'history-row',$('history-list'));const info=node('div',undefined,'',row);node('h3',item.request?.store?.name||'지역 리서치','',info);node('p',`${item.request?.campaign?.product||'접수한 조사'} · ${new Date(item.created_at).toLocaleString('ko-KR')} · ${({queued:'대기',running:'진행',completed:'완료',failed:'실패'})[item.status]||'상태 확인 중'}`,'',info);const button=node('button','열기 ↗','text-button',row);button.addEventListener('click',()=>{clearTimeout(timer);activeJob=item.job_id;lastRequest=item.request;pending=null;polls=0;clearResult();save();show('overview');poll();});}}
function clearResult(){cached=null;markdown='';$('download').disabled=true;$('overview-content').hidden=true;for(const id of ['quant-cards','local-cards','context-cards','trend-cards','source-list','brief'])empty($(id));$('quality').textContent='완료된 결과에서 자료·검토 상태를 확인할 수 있어요.';}
async function poll(){clearTimeout(timer);const job=activeJob;try{const data=await api(`/api/research/${job}`);if(job!==activeJob)return;$('resume').hidden=true;if(data.status==='completed'){notice('조사가 완료됐어요. 신호 카드를 선택해 근거를 확인해주세요.');display(data);$('submit').disabled=false;pending=null;remember('completed');return;}if(data.status==='failed'){notice('조사를 완료하지 못했어요. 연결과 입력을 확인한 뒤 새 조사를 시작해주세요.',true);progress('failed');$('submit').disabled=false;pending=null;remember('failed');return;}progress(data.status,{},data.progress?.stages||{});remember(data.status);notice(data.status==='queued'?'조사를 접수했어요. 앞선 작업이 끝나면 시작합니다.':'지역과 고객 맥락을 조사하고 있어요. 결과가 도착하면 신호와 근거를 표시합니다.');if(++polls>=120){notice('조사가 계속 진행 중이에요. 잠시 뒤 결과 조회를 다시 시도해주세요.');$('resume').hidden=false;return;}timer=setTimeout(poll,5000);}catch(error){if(job!==activeJob)return;notice(errors[error.message]||'결과를 불러오지 못했어요.',true);$('resume').hidden=false;}}
async function send(){$('submit').disabled=true;$('retry').hidden=true;notice('조사를 접수하고 있어요…');progress('connecting');show('overview');try{const data=await api('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pending)});activeJob=data.job_id;polls=0;remember(data.status);await poll();}catch(error){notice(errors[error.message]||'요청을 접수하지 못했어요.',true);$('submit').disabled=false;$('retry').hidden=false;}}
$('research-form').addEventListener('submit',event=>{event.preventDefault();const f=new FormData(event.target),lat=f.get('lat'),lng=f.get('lng');if(Boolean(lat)!==Boolean(lng)){$('form-error').hidden=false;$('form-error').textContent='위도와 경도를 함께 입력해주세요.';return;}clearTimeout(timer);pending={schema_version:'0.1',request_id:'web-'+crypto.randomUUID(),requested_at:new Date().toISOString(),store:{name:f.get('name').trim(),address:f.get('address').trim(),lat:lat?Number(lat):null,lng:lng?Number(lng):null},campaign:{purpose:f.get('purpose').trim(),product:f.get('product').trim(),target_hint:f.get('target_hint').trim()||null},research:{reference_date:f.get('reference_date'),radius_m:Number(f.get('radius_m')),lookback_days:Number(f.get('lookback_days'))}};lastRequest=pending;activeJob=null;clearResult();save();$('request-dialog').close();send();});
$('retry').addEventListener('click',()=>{if(pending)send();});$('resume').addEventListener('click',()=>{polls=0;poll();});$('download').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([markdown],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='SPOT-research-brief.md';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function init(){clearResult();try{const config=await api('/api/config');document.querySelector('[name=reference_date]').value=config.reference_date;const saved=JSON.parse(sessionStorage.getItem('spot-work')||'null');history=Array.isArray(saved?.history)?saved.history:[];lastRequest=saved?.lastRequest||saved?.pending||null;if(saved?.activeJob){pending=saved.pending;activeJob=saved.activeJob;progress('connecting');$('submit').disabled=Boolean(pending);await poll();}else if(saved?.pending){pending=saved.pending;notice('접수 결과가 확인되지 않은 요청이 있어요. 같은 요청으로 다시 연결할 수 있어요.');$('retry').hidden=false;}renderHistory();heading();}catch{notice('화면을 준비하지 못했어요. 새로고침해주세요.',true);}}init();
}
