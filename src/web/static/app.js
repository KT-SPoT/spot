'use strict';
// Local presentation only: percentages come from evidence cards, never from peak labels.
const SPOTQuantCharts = (() => {
  const kinds = {floating_population:'유동인구',resident_population:'주거인구',worker_population:'직장인구',sales:'매출액'};
  const dimensions = {
    gender:{title:'성별 구성',keys:['male','female'],labels:['남성','여성']},
    age:{title:'연령 구성',keys:['under_10','teens','20s','30s','40s','50s','60_plus'],labels:['10세 미만','10대','20대','30대','40대','50대','60대 이상']},
    day:{title:'요일별 비중',keys:['mon','tue','wed','thu','fri','sat','sun'],labels:['월요일','화요일','수요일','목요일','금요일','토요일','일요일']},
    time:{title:'시간대별 비중',keys:['05_09','09_12','12_14','14_18','18_23','23_05'],labels:['05~09시','09~12시','12~14시','14~18시','18~23시','23~05시']}
  };
  const percent = value => typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100;
  const number = value => typeof value==='number'&&Number.isFinite(value);
  const format = value => value.toLocaleString('ko-KR',{maximumFractionDigits:2});
  function rows(card,dimension,kind){
    const def=dimensions[dimension];
    return def.keys.flatMap((key,i)=>(dimension==='age'&&(
      (kind!=='resident_population'&&key==='under_10')||(kind==='worker_population'&&key==='teens')))?[]:[{
      key,label:def.labels[i],value:percent(card?.shares?.[key]?.share_pct)?card.shares[key].share_pct:null,
      count:number(card?.shares?.[key]?.count)&&card.shares[key].count>=0?card.shares[key].count:null
    }]);
  }
  function chartCard(cards,kind,dimension){
    return cards.find(c=>c.population_kind===kind&&c.distribution_kind===dimension&&Array.isArray(c.sources)&&c.sources.length)
      ||(['gender','age'].includes(dimension)?cards.find(c=>c.population_kind===kind&&!c.distribution_kind&&c.shares&&Array.isArray(c.sources)&&c.sources.length):null);
  }
  // All visual geometry uses the returned shares. Missing observations remain missing.
  function draw(doc,parent,data,dimension,kind){
    const make=(tag,text,cls,host)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;if(host)host.append(el);return el;};
    const known=data.filter(r=>r.value!==null),max=Math.max(0,...known.map(r=>r.value));
    if(dimension==='gender'&&known.length===data.length&&Math.abs(known.reduce((s,r)=>s+r.value,0)-100)<0.01){
      const wrap=make('div',undefined,'quant-gender',parent);
      const ring=make('div',undefined,'quant-donut',wrap);ring.setAttribute('role','img');ring.setAttribute('aria-label',data.map(r=>`${r.label} ${format(r.value)}%`).join(', '));
      ring.style.background=`conic-gradient(var(--chart-primary,#315a50) 0% ${data[0].value}%, var(--chart-secondary,#b69278) ${data[0].value}% 100%)`;
      make('span',kinds[kind],'quant-donut-center',ring);
      const legend=make('div',undefined,'quant-gender-legend',wrap);
      data.forEach((row,i)=>{const item=make('div',undefined,'quant-gender-item tone-'+i,legend);make('span',row.label,'',item);make('strong',format(row.value)+'%','',item);if(row.count!==null)make('small',format(row.count)+'명','',item);});
      return;
    }
    if(dimension==='age'||dimension==='day'){
      // Labeled scale starts at zero; the upper bound rounds up to the next 10%.
      const ceiling=Math.max(10,Math.ceil(max/10)*10);
      const chart=make('div',undefined,'quant-plot '+(dimension==='day'?'is-lollipop':'is-column'),parent);
      chart.setAttribute('role','img');chart.setAttribute('aria-label',data.map(r=>`${r.label} ${r.value===null?'미확보':format(r.value)+'%'}`).join(', '));
      const axis=make('div',undefined,'quant-axis',chart);for(const value of [ceiling,ceiling/2,0])make('span',format(value)+'%','',axis);
      const columns=make('div',undefined,'quant-columns',chart);
      for(const row of data){
        const item=make('div',undefined,'quant-column'+(row.value===max?' is-top':'')+(row.value===null?' is-missing':''),columns);
        const track=make('div',undefined,'quant-column-track',item);track.setAttribute('aria-hidden','true');
        if(row.value!==null){const fill=make('div',undefined,'quant-column-fill',track);fill.style.height=(row.value/ceiling*100)+'%';make('strong',format(row.value)+'%','quant-column-value',fill);}
        else make('span','미확보','quant-column-missing',track);
        make('span',row.label.replace('요일','').replace(' 이상','+'),'quant-column-label',item);
      }
      return;
    }
    if(dimension==='time'){
      const band=make('div',undefined,'quant-time-band '+(kind==='sales'?'is-sales':'is-floating'),parent);
      for(const row of data){const cell=make('div',undefined,'quant-time-cell'+(row.value===max?' is-top':'')+(row.value===null?' is-missing':''),band);
        if(row.value!==null)cell.style.backgroundColor=kind==='sales'?`rgba(237,170,71,${0.12+row.value/100*0.88})`:`rgba(56,104,245,${0.12+row.value/100*0.88})`;
        make('strong',row.value===null?'미확보':format(row.value)+'%','',cell);make('span',row.label,'',cell);
      }
      return;
    }
    // An incomplete or non-100% gender table cannot be represented as a full donut.
    const bars=make('div',undefined,'quant-bars',parent);
    for(const row of data){const line=make('div',undefined,'quant-bar-row'+(row.value===max?' is-top':''),bars);make('span',row.label,'quant-bar-label',line);const track=make('div',undefined,'quant-bar-track'+(row.value===null?' is-missing':''),line);track.setAttribute('aria-hidden','true');if(row.value!==null){const fill=make('span',undefined,'quant-bar-fill',track);fill.style.width=row.value+'%';}make('strong',row.value===null?'미확보':format(row.value)+'%','quant-bar-number',line);}
  }
  function preview(doc,target,cards,evidence){
    target.replaceChildren();
    const make=(tag,text,cls,parent)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;if(parent)parent.append(el);return el;};
    const head=make('div',undefined,'overview-panel-head',target);make('h3','누가 이 지역을 찾을까요?','',head);
    const tabs=make('div',undefined,'quant-tabs compact',head),content=make('div',undefined,'overview-age-content',target);
    function select(kind){for(const button of tabs.children)button.setAttribute('aria-pressed',String(button.dataset.kind===kind));content.replaceChildren();const card=chartCard(cards,kind,'age'),data=rows(card,'age',kind),known=data.filter(r=>r.value!==null);
      if(!known.length){make('p','이 모집단의 연령 비율은 미확보됐어요.','empty',content);return;}
      const max=Math.max(...known.map(r=>r.value)),top=known.filter(r=>r.value===max).map(r=>r.label).join(' · ');
      make('p',`${kinds[kind]} · ${known.length<data.length?'확보 항목 중 ':''}${top} ${format(max)}%`,'quant-chart-lead',content);draw(doc,content,data,'age',kind);
      make('p','자료 기준 · '+(card.reference_period||'미확인'),'quant-chart-note',content);
      const button=make('button','분포의 출처 보기 ↗','text-button',content);button.type='button';button.addEventListener('click',()=>evidence(card,'quant'));
    }
    for(const kind of ['floating_population','resident_population','worker_population']){const button=make('button',kinds[kind].replace('인구',''),' ',tabs);button.type='button';button.dataset.kind=kind;button.addEventListener('click',()=>select(kind));}
    select(['floating_population','resident_population','worker_population'].find(k=>rows(chartCard(cards,k,'age'),'age',k).some(r=>r.value!==null))||'floating_population');
  }
  function render(doc,target,cards,evidence){
    target.replaceChildren();target.className='quant-dashboard';
    if(!cards.length){
      const message=doc.createElement('p');message.className='empty';
      message.textContent='이번 조사에서 상권 자료를 확보하지 못했어요.';target.append(message);return;
    }
    const make=(tag,text,cls,parent)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;if(parent)parent.append(el);return el;};
    const summary=make('div',undefined,'quant-kpis',target);
    for(const [metric,label,unit] of [['daily_avg_floating_population','일평균 유동인구','명'],['resident_population','주거인구','명'],['worker_population','직장인구','명'],['monthly_avg_sales_10k_krw','업소당 월평균 매출','만원']]){
      const card=cards.find(c=>c.metric_refs?.includes(metric)&&number(c.value)&&c.value>=0&&c.sources?.length);
      const kpi=make('article',undefined,'quant-kpi',summary);make('p',label,'',kpi);
      const line=make('div',undefined,'quant-kpi-value',kpi);make('strong',card?format(card.value):'—','',line);if(card)make('span',unit,'',line);
      make('small',card?`자료 기준 · ${card.reference_period||'미확인'}`:'자료 미확보','',kpi);
      if(card){const button=make('button','근거 보기 ↗','text-button',kpi);button.type='button';button.addEventListener('click',()=>evidence(card,'quant'));}
    }
    const section=make('section',undefined,'quant-analysis',target);
    const header=make('div',undefined,'quant-section-head',section);make('div','고객 구성과 방문 맥락','quant-heading',header);make('span','소상공인365 · 공공 관측값','quant-scale',header);
    const tabs=make('div',undefined,'quant-tabs',section);tabs.setAttribute('aria-label','분석 모집단 선택');
    const content=make('div',undefined,'quant-tab-content',section);
    let selected=Object.keys(kinds).find(kind=>Object.keys(dimensions).some(d=>rows(chartCard(cards,kind,d),d,kind).some(r=>r.value!==null)))||'floating_population';
    function select(kind){
      selected=kind;for(const button of tabs.children)button.setAttribute('aria-pressed',String(button.dataset.kind===kind));
      content.replaceChildren();
      make('p',kind==='sales'?'매출액의 구성비입니다. 방문자 수·매출건수 비율과 구분해 읽어주세요.':'선택 영역의 '+kinds[kind]+' 구성입니다. 성별·연령은 각각의 분포이며 교차 고객 비율이나 행사 선호를 뜻하지 않습니다.','quant-context',content);
      const grid=make('div',undefined,'quant-chart-grid',content);
      for(const dimension of ['age','gender','time','day']){
        const def=dimensions[dimension];
        if(['resident_population','worker_population'].includes(kind)&&['day','time'].includes(dimension))continue;
        const card=chartCard(cards,kind,dimension),data=rows(card,dimension,kind),known=data.filter(r=>r.value!==null);
        const panel=make('article',undefined,'quant-chart dimension-'+dimension,grid);panel.setAttribute('aria-label',kinds[kind]+' '+def.title);
        make('p',kinds[kind]+' · '+(kind==='sales'?'매출액 비율':'인구 비율'),'eyebrow',panel);make('h3',def.title,'',panel);
        if(!known.length){
          const peakMetric=dimension==='day'?'peak_'+(kind==='sales'?'sales':'floating')+'_day':dimension==='time'?'peak_'+(kind==='sales'?'sales':'floating')+'_time_band':null;
          const peak=cards.find(c=>peakMetric&&c.metric_refs?.includes(peakMetric)&&c.sources?.length);
          make('p',peak?`${peak.title}: ${peak.value}`:'제공 비율 미확보','quant-unavailable',panel);
          make('p','전체 분포를 확인할 비율이 없어 그래프를 표시하지 않습니다.','quant-chart-note',panel);
          if(peak){const button=make('button','확보한 관측값 근거 ↗','text-button',panel);button.type='button';button.addEventListener('click',()=>evidence(peak,'quant'));}
          continue;
        }
        const max=Math.max(...known.map(r=>r.value)),top=known.filter(r=>r.value===max);
        make('p',`${known.length===data.length?'가장 높은 비중':'확보 항목 중 가장 높은 비중'} · ${top.map(r=>r.label).join(' · ')} ${format(max)}%`,'quant-chart-lead',panel);
        draw(doc,panel,data,dimension,kind);
        if(dimension==='time'){
          const otherKind=kind==='sales'?'floating_population':'sales',other=chartCard(cards,otherKind,'time'),otherData=rows(other,'time',otherKind);
          if(other&&otherData.some(r=>r.value!==null)){
            make('p',kinds[otherKind]+' · 별도 제공 표의 비중','quant-comparison-label',panel);draw(doc,panel,otherData,dimension,otherKind);
            make('p',`${kinds[otherKind]} 자료 기준 · ${other.reference_period||'미확인'} / ${other.scope||'지역 범위 미확인'} · 서로 다른 모집단의 분포입니다.`,'quant-chart-note',panel);
            const otherButton=make('button',kinds[otherKind]+' 출처 보기 ↗','text-button',panel);otherButton.type='button';otherButton.addEventListener('click',()=>evidence(other,'quant'));
          }
        }
        make('p',`자료 기준 · ${card.reference_period||'미확인'} / ${card.scope||'지역 범위 미확인'}`,'quant-chart-note',panel);
        const total=known.reduce((sum,r)=>sum+r.value,0);
        if(known.length<data.length)make('p','일부 항목이 미확보입니다. 미확보를 0%로 처리하거나 합계를 100%로 환산하지 않습니다.','quant-chart-note',panel);
        else if(Math.abs(total-100)>1)make('p',`제공 비율 합계 ${format(total)}% · 원문 비율을 그대로 표시합니다.`,'quant-chart-note',panel);
        const footer=make('div',undefined,'quant-chart-footer',panel);
        const button=make('button','출처 · 근거 보기 ↗','text-button',footer);button.type='button';button.addEventListener('click',()=>evidence(card,'quant'));
        const details=make('details',undefined,'quant-data-table',panel);make('summary','수치 표 보기','',details);
        const table=make('table',undefined,'',details);make('caption',kinds[kind]+' '+def.title+' 원래 관측값','',table);
        const head=make('thead',undefined,'',table),headrow=make('tr',undefined,'',head);
        for(const label of ['구분','비율','인구(확보 시)']){const th=make('th',label,'',headrow);th.setAttribute('scope','col');}
        const body=make('tbody',undefined,'',table);
        for(const row of data){const tr=make('tr',undefined,'',body);const th=make('th',row.label,'',tr);th.setAttribute('scope','row');make('td',row.value===null?'미확보':format(row.value)+'%','',tr);make('td',row.count===null?'미확보':format(row.count)+'명','',tr);}
      }
    }
    for(const [kind,label] of Object.entries(kinds)){
      const button=make('button',label,'',tabs);button.type='button';button.dataset.kind=kind;button.addEventListener('click',()=>select(kind));
    }
    select(selected);
    const extra=cards.filter(c=>!c.shares&&c.metric_refs?.length);
    if(extra.length){const details=make('details',undefined,'quant-other',target);make('summary','전체 상권 관측값 · '+extra.length+'개','',details);
      for(const card of extra){const row=make('div',undefined,'quant-observation',details);make('span',card.title,'',row);make('strong',number(card.value)?format(card.value)+(card.unit||''):String(card.value??'미확보'),'',row);const button=make('button','근거 ↗','text-button',row);button.type='button';button.addEventListener('click',()=>evidence(card,'quant'));}}
  }
  return {render,rows,chartCard,draw,preview};
})();


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
if (typeof module !== 'undefined') module.exports = {renderBrief, SPOTQuantCharts};

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
function heading(){const request=lastRequest;const store=request?.store?.name||cached?.result?.research_brief?.overview?.area_summary?.split(':')[0];const product=request?.campaign?.product;$('context-label').textContent=store?`${store}${product?' × '+product:''}`:activeJob?'CURRENT RESEARCH':'EXPLORE YOUR NEXT SPOT';$('page-title').textContent=current==='overview'?(store|| (activeJob?'지역 리서치 워크스페이스':'어디에서 캠페인을 시작할까요?')):labels[current];$('page-description').textContent=request?.store?.address||'매장에서 시작해, 지역·고객 맥락과 전국 체험 사례의 연결점을 발견하세요.';}
function show(view){if(!labels[view])return;if(typeof SPOTExperience!=='undefined')SPOTExperience.workspace(view!=='overview'||Boolean(activeJob||pending));current=view;document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${view}`);document.querySelectorAll('.nav-item').forEach(el=>{if(el.dataset.view===view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});$('current-view').textContent=labels[view];heading();if(view==='history')renderHistory();}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>show(button.dataset.view)));
document.querySelectorAll('[data-new]').forEach(button=>button.addEventListener('click',()=>{$('form-error').hidden=true;$('request-dialog').showModal();}));
$('close-request').addEventListener('click',()=>$('request-dialog').close());$('close-evidence').addEventListener('click',()=>$('evidence-dialog').close());
function sourceRow(source,target,module){const row=node('div',undefined,'source-row',target);let url;try{url=new URL(source.source_url);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)url=null;}catch{url=null;}if(url){const a=node('a',source.title||source.source_name||url.hostname,'',row);a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';}else node('strong',source.source_name||'출처 주소 미확보','',row);node('p',`${module?module.toUpperCase()+' · ':''}${source.source_id||''} · 게시일 ${source.published_at||'미확인'} · 수집일 ${source.collected_at||'미확인'}`,'',row);}
function trendReasoning(card,target){if(card.type!=='reference_case')return;for(const reason of card.why_relevant||[])node('p',reason,'',target);const labels={floating_population:'유동인구',resident_population:'주거인구',worker_population:'직장인구',sales:'매출 비중'};for(const fit of card.audience_fit||[]){const detail=node('details',undefined,'',target);node('summary',`${labels[fit.population_kind]||'관측 구성'} · 매장 응용 검토`,'',detail);node('p',fit.rationale||'','',detail);node('p',fit.next_check||'','',detail);}}
function evidence(card,module){$('evidence-title').textContent=card.title||card.event_name||card.name||'조사 신호';$('evidence-statement').textContent=card.statement||card.evidence||card.observation||card.description||'';$('evidence-meta').replaceChildren();const context=[`Used by · ${module.toUpperCase()} Scout`,card.scope&&`해석 범위 · ${card.scope}`,`자료 기준 · ${card.reference_period||'미확인'}`,card.type==='reference_case'?'연결 수준 · 체험 참고 사례 / 매장 응용은 조사 가설':'자료 수준 · 제공 관측값·보도 맥락을 확인하세요.'];for(const text of context.filter(Boolean))node('p',text,'',$('evidence-meta'));trendReasoning(card,$('evidence-meta'));for(const facet of card.supporting_facets||[])node('p',`관련 보도 · ${facet.published_at||'날짜 미확인'} · ${facet.change_state==='scheduled'?'예정':facet.change_state==='reported_repair_or_reopening'?'정비 완료·통행 재개 보도':facet.change_state||'단계 미확인'} · ${facet.evidence||''}`,'',$('evidence-meta'));$('evidence-sources').replaceChildren();const sources=card.sources||[];if(!sources.length)empty($('evidence-sources'),'연결된 출처가 없습니다.');for(const source of sources)sourceRow(source,$('evidence-sources'),module);for(const [key,items] of Object.entries(card.context_sources||{}))for(const source of items)sourceRow(source,$('evidence-sources'),key);$('evidence-dialog').showModal();}
function cards(target,items,module){target.replaceChildren();if(!items.length){empty(target,'이번 조사에서 이 항목에 사용할 수 있는 근거를 확보하지 못했어요.');return;}for(const card of items){const box=node('article',undefined,'signal-card',target);node('p',module.toUpperCase()+' SIGNAL','eyebrow',box);node('h3',card.title||card.event_name||card.name||'조사 신호','',box);if(card.value!==undefined)node('p',`${typeof card.value==='number'?card.value.toLocaleString('ko-KR'):card.value}${card.unit||''}`,'value-line',box);node('p',card.statement||card.evidence||card.observation||card.description||card.summary||'근거와 해석 범위를 함께 확인하세요.','',box);const adaptation=card.adaptation_hypotheses;if(Array.isArray(adaptation)&&adaptation[0])node('p',typeof adaptation[0]==='string'?adaptation[0]:adaptation[0].statement||'','',box);const footer=node('div',undefined,'card-footer',box);node('span',`${(card.sources||[]).length}개 연결 근거`,'',footer);const button=node('button','근거 보기 ↗','evidence-button',footer);button.type='button';button.addEventListener('click',()=>evidence(card,module));}}
function progress(status,moduleStatus={},stages={}){$('welcome').hidden=true;$('research-workspace').hidden=false;$('overview-content').hidden=status!=='completed';$('progress-title').textContent=status==='completed'?'Research complete':'Researching this SPoT';$('job-state').textContent=({queued:'접수 · 대기',running:'조사 진행 중',completed:'브리프 생성 완료',failed:'실행 실패',connecting:'연결 중'})[status]||'상태 확인 중';$('scout-cards').replaceChildren();for(const [key,info] of Object.entries(modules)){const state=moduleStatus[key];const card=node('article',undefined,'scout-card',$('scout-cards'));node('div',info.icon,'scout-icon',card);node('span',state?({success:'✓ 자료 확보',partial:'일부 자료 확보',failed:'자료 미확보'}[state]||'상태 미확인'):(status==='failed'?'상태 미확인':'완료 결과 대기'),'scout-state '+(state||''),card);node('div',key.toUpperCase()+' SCOUT','scout-label',card);node('h3',info.name,'',card);node('p',info.description,'',card);}$('progress-note').textContent=status==='completed'?'확보한 자료와 조사 가설을 구분해 확인하세요. 일부 자료 미확보가 있어도 브리프는 보존됩니다.':'상권·지역 조사 → 체험 트렌드 탐색 → 연결·차별성 검토 순서로 조사합니다. 항목별 자료와 발견한 신호는 조사가 완료되면 표시합니다.';if(typeof SPOTExperience!=='undefined')SPOTExperience.progress(status,stages);}
function criticLabel(review,diagnostics={}){if(review.performed){const rows=review.case_reviews||[];return '고객 연결·차별성 검토 완료'+(rows.length?` · 응용 보완 ${rows.filter(r=>r.verdict!=='useful').length}/${rows.length}건`:'');}return diagnostics.gpt_status==='disabled'||review.code==='DISABLED'?'GPT 검토 꺼짐':diagnostics.gpt_status==='incomplete'||review.code?'GPT 검토 미완료 · '+(review.code||diagnostics.gpt_code||'상태 확인 필요'):'GPT 검토 상태 미확인';}
function display(data){cached=data;const result=data.result||{},brief=result.research_brief||{},review=brief.research_review||{};markdown=result.research_brief_markdown||'조사 결과 본문이 없습니다.';progress('completed',result.module_status);$('area-title').textContent=lastRequest?.store?.name||'조사 지역의 근거 요약';$('area-summary').textContent=brief.overview?.area_summary||'지역 요약이 없습니다.';$('customer-signal').textContent=brief.overview?.primary_customer_signal||'인구 신호를 요약할 자료가 미확보됐어요.';$('source-count').textContent=`${brief.source_count||0}개 고유 출처`;$('why-now').textContent=brief.why_here_now||'판단할 근거가 미확보됐어요.';$('quality').textContent=(result.mode==='offline'?'외부 호출 없는 연결 확인 결과 · ':'')+criticLabel(review,result.critic_result?.checks?.diagnostics)+` · ${brief.source_count||0}개 출처 연결. 확보한 조사 자료를 보존하며 사실·고객 호응·행사 효과의 최종 인증을 뜻하지 않습니다.`;
const signals=brief.unique_local_signals||[],quant=signals.filter(card=>card.module==='quant'),local=brief.local_changes||[],context=signals.filter(card=>card.module!=='quant'),trend=brief.trend_patterns||[];if(typeof SPOTQuantCharts!=='undefined')SPOTQuantCharts.render(document,$('quant-cards'),quant,evidence);else cards($('quant-cards'),quant,'quant');cards($('local-cards'),local,'local');cards($('context-cards'),context,'local');cards($('trend-cards'),trend,'trend');$('signal-cards').replaceChildren();const featured=[...quant.slice(0,2).map(card=>[card,'quant']),...local.slice(0,2).map(card=>[card,'local']),...trend.filter(card=>card.type==='reference_case').slice(0,2).map(card=>[card,'trend'])];if(!featured.length)empty($('signal-cards'));for(const [card,module] of featured){const staging=document.createElement('div');cards(staging,[card],module);$('signal-cards').append(...staging.children);}renderBrief(document,$('brief'),markdown);for(const title of $('brief').querySelectorAll('summary'))if(title.textContent.startsWith('Critic:'))title.textContent='고객 연결·차별성 검토';for(const id of ['download','download-md','download-handoff'])$(id).disabled=false;$('source-list').replaceChildren();const seen=new Set();for(const [items,module] of [[quant,'quant'],[local.concat(context),'local'],[trend,'trend']])for(const card of items){for(const source of card.sources||[]){const id=`${module}:${source.source_id}:${source.source_url}`;if(!seen.has(id)){seen.add(id);sourceRow(source,$('source-list'),module);}}for(const [key,items] of Object.entries(card.context_sources||{}))for(const source of items){const id=`${key}:${source.source_id}:${source.source_url}`;if(!seen.has(id)){seen.add(id);sourceRow(source,$('source-list'),key);}}}if(!seen.size)empty($('source-list'),'이용 가능한 출처가 없습니다.');if(typeof SPOTExperience!=='undefined')SPOTExperience.display(brief,lastRequest,sourceRow,evidence);if(typeof SPOTTrendBoard!=='undefined'){ $('trend-cards').classList.add('trend-board');SPOTTrendBoard.render(document,$('trend-cards'),brief,lastRequest,evidence,result.trend_discovery||{});}heading();}
function remember(status){const entry=history.find(item=>item.job_id===activeJob);if(entry)entry.status=status;else history.unshift({job_id:activeJob,status,request:lastRequest,created_at:new Date().toISOString()});history=history.slice(0,4);save();}
function renderHistory(){$('history-list').replaceChildren();if(!history.length){empty($('history-list'),'이 탭에서 접수한 리서치가 아직 없습니다.');return;}for(const item of history){const row=node('article',undefined,'history-row',$('history-list'));const info=node('div',undefined,'',row);node('h3',item.request?.store?.name||'지역 리서치','',info);node('p',`${item.request?.campaign?.product||'접수한 조사'} · ${new Date(item.created_at).toLocaleString('ko-KR')} · ${({queued:'대기',running:'진행',completed:'완료',failed:'실패'})[item.status]||'상태 확인 중'}`,'',info);const button=node('button','열기 ↗','text-button',row);button.addEventListener('click',()=>{clearTimeout(timer);activeJob=item.job_id;lastRequest=item.request;pending=null;polls=0;clearResult();save();show('overview');poll();});}}
function clearResult(){cached=null;markdown='';for(const id of ['download','download-md','download-handoff'])$(id).disabled=true;$('overview-content').hidden=true;for(const id of ['quant-cards','local-cards','context-cards','trend-cards','source-list','brief'])empty($(id));$('quality').textContent='완료된 결과에서 자료·검토 상태를 확인할 수 있어요.';}
async function poll(){clearTimeout(timer);const job=activeJob;try{const data=await api(`/api/research/${job}`);if(job!==activeJob)return;$('resume').hidden=true;if(data.status==='completed'){notice('조사가 완료됐어요. 신호 카드를 선택해 근거를 확인해주세요.');display(data);$('submit').disabled=false;pending=null;remember('completed');return;}if(data.status==='failed'){notice('조사를 완료하지 못했어요. 연결과 입력을 확인한 뒤 새 조사를 시작해주세요.',true);progress('failed');$('submit').disabled=false;pending=null;remember('failed');return;}progress(data.status,{},data.progress?.stages||{});remember(data.status);notice(data.status==='queued'?'조사를 접수했어요. 앞선 작업이 끝나면 시작합니다.':'지역과 고객 맥락을 조사하고 있어요. 결과가 도착하면 신호와 근거를 표시합니다.');if(++polls>=120){notice('조사가 계속 진행 중이에요. 잠시 뒤 결과 조회를 다시 시도해주세요.');$('resume').hidden=false;return;}timer=setTimeout(poll,5000);}catch(error){if(job!==activeJob)return;notice(errors[error.message]||'결과를 불러오지 못했어요.',true);$('resume').hidden=false;}}
async function send(){$('submit').disabled=true;$('retry').hidden=true;notice('조사를 접수하고 있어요…');progress('connecting');show('overview');try{const data=await api('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pending)});activeJob=data.job_id;polls=0;remember(data.status);await poll();}catch(error){notice(errors[error.message]||'요청을 접수하지 못했어요.',true);$('submit').disabled=false;$('retry').hidden=false;}}
$('research-form').addEventListener('submit',event=>{event.preventDefault();const f=new FormData(event.target),lat=f.get('lat'),lng=f.get('lng');if(Boolean(lat)!==Boolean(lng)){$('form-error').hidden=false;$('form-error').textContent='위도와 경도를 함께 입력해주세요.';return;}clearTimeout(timer);pending={schema_version:'0.1',request_id:'web-'+crypto.randomUUID(),requested_at:new Date().toISOString(),store:{name:f.get('name').trim(),address:f.get('address').trim(),lat:lat?Number(lat):null,lng:lng?Number(lng):null},campaign:{purpose:'매장 지역·고객 맥락 리서치',product:null,target_hint:null},research:{reference_date:f.get('reference_date'),radius_m:Number(f.get('radius_m')),lookback_days:Number(f.get('lookback_days'))}};lastRequest=pending;activeJob=null;clearResult();save();$('request-dialog').close();send();});
$('retry').addEventListener('click',()=>{if(pending)send();});$('resume').addEventListener('click',()=>{polls=0;poll();});
function downloadBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('download-md').addEventListener('click',()=>downloadBlob(new Blob([markdown],{type:'text/markdown;charset=utf-8'}),'SPOT-research-brief.md'));
async function downloadExport(button,path,name){if(!activeJob)return;button.disabled=true;try{const response=await fetch(`/api/research/${encodeURIComponent(activeJob)}/${path}`);if(!response.ok){notice(response.status===401?'접속이 만료됐어요. 결과를 조회한 접속에서 다시 시도해주세요.':'파일을 준비하지 못했어요. 결과 조회를 다시 시도해주세요.',true);return;}downloadBlob(await response.blob(),name);}catch{notice('내보내기 서버에 연결하지 못했어요.',true);}finally{button.disabled=!cached;}}
$('download').addEventListener('click',()=>downloadExport($('download'),'pdf','SPOT-research-brief.pdf'));
$('download-handoff').addEventListener('click',()=>downloadExport($('download-handoff'),'handoff','SPOT-heung-manager-prompt.txt'));
async function init(){clearResult();try{const config=await api('/api/config');document.querySelector('[name=reference_date]').value=config.reference_date;const saved=JSON.parse(sessionStorage.getItem('spot-work')||'null');history=Array.isArray(saved?.history)?saved.history:[];lastRequest=saved?.lastRequest||saved?.pending||null;if(saved?.activeJob){pending=saved.pending;activeJob=saved.activeJob;progress('connecting');$('submit').disabled=Boolean(pending);await poll();}else if(saved?.pending){pending=saved.pending;notice('접수 결과가 확인되지 않은 요청이 있어요. 같은 요청으로 다시 연결할 수 있어요.');$('retry').hidden=false;}renderHistory();heading();}catch{notice('화면을 준비하지 못했어요. 새로고침해주세요.',true);}}init();
}
