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

if (typeof document !== "undefined") {
'use strict';
const $ = id => document.getElementById(id);
let pending = null, activeJob = null, timer = null, markdown = '', polls = 0;
const errors = {CONNECTION_AUTH:'서버 연결 인증을 확인해야 해요.',CONNECTION_UNAVAILABLE:'조사 서버에 연결할 수 없어요. PC와 개발 터널이 켜져 있는지 확인해주세요.',SESSION_EXPIRED:'접속 시간이 만료됐어요. 페이지를 새로 열어주세요.',INVALID_REQUEST:'입력 항목과 좌표를 확인해주세요.',JOB_NOT_FOUND:'작업이 만료됐거나 이 화면에서 접수한 작업이 아니에요.',REQUEST_CONFLICT:'같은 요청 번호에 다른 입력이 들어왔어요. 새 조사를 시작해주세요.',BUSY:'조사 대기열이 가득 찼어요. 잠시 뒤 같은 요청을 다시 연결해주세요.',SESSION_JOB_LIMIT:'이 접속에서 조사 4건을 접수했어요. 진행 중인 결과를 먼저 확인해주세요.'};
function notice(text, error=false){$('notice').hidden=false;$('notice').textContent=text;$('notice').className=error?'error':'';}
async function api(path, options){let response;try{response=await fetch(path, {...options, signal:AbortSignal.timeout(25000)});}catch{throw new Error('CONNECTION_UNAVAILABLE');}let data;try{data=await response.json();}catch{throw new Error('CONNECTION_UNAVAILABLE');}if(!response.ok)throw new Error(data.error?.code||'CONNECTION_UNAVAILABLE');return data;}
function save(){sessionStorage.setItem('spot-work',JSON.stringify({pending,activeJob}));}
function display(data){const result=data.result||{}, brief=result.research_brief||{}, review=brief.research_review||{};markdown=result.research_brief_markdown||'조사 결과 본문이 없습니다.';$('result').hidden=false;$('result-title').textContent='지역과 경험을 연결한 연구 브리프';$('overview').textContent=brief.overview?.area_summary||'';$('quality').textContent=(result.mode==='offline'?'외부 호출 없는 연결 확인 결과입니다. ':'')+(review.performed?'GPT 고객 연결·차별성 검토가 포함돼 있어요.':'GPT 검토가 미완료이거나 꺼져 있어요. 확보한 조사 자료는 아래에 보존돼 있어요.')+' 조사 완료는 고객 선호나 행사 효과가 입증됐다는 뜻은 아닙니다.';renderBrief(document,$('brief'),markdown);$('module-status').replaceChildren();const labels={quant:'상권·고객 구성',local:'지역 변화',trend:'전국 체험 트렌드'},status={success:'자료 확보',partial:'일부 자료 확보',failed:'자료 미확보'};for(const [key,value] of Object.entries(result.module_status||{})){const tag=document.createElement('span');tag.textContent=`${labels[key]||key} · ${status[value]||value}`;$('module-status').append(tag);}}
async function poll(){clearTimeout(timer);try{const data=await api(`/api/research/${activeJob}`);$('resume').hidden=true;if(data.status==='completed'){notice('조사가 완료됐어요. 근거와 검토 상태를 함께 확인해주세요.');display(data);$('submit').disabled=false;pending=null;save();return;}if(data.status==='failed'){notice('조사를 완료하지 못했어요. 입력과 연결 상태를 확인한 뒤 새 조사를 시작해주세요.',true);$('submit').disabled=false;pending=null;save();return;}notice(data.status==='queued'?'조사를 접수했어요. 앞선 작업이 끝나면 시작합니다.':'상권·지역·트렌드를 조사하고 있어요. 완료되면 브리프를 표시합니다.');if(++polls>=120){notice('조사가 계속 진행 중이에요. 잠시 뒤 결과 조회를 다시 시도해주세요.');$('resume').hidden=false;return;}timer=setTimeout(poll,5000);}catch(error){notice(errors[error.message]||'결과를 불러오지 못했어요.',true);$('resume').hidden=false;}}
async function send(){ $('submit').disabled=true;$('retry').hidden=true;notice('조사를 접수하고 있어요…');try{const data=await api('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pending)});activeJob=data.job_id;polls=0;save();await poll();}catch(error){notice(errors[error.message]||'요청을 접수하지 못했어요.',true);$('submit').disabled=false;$('retry').hidden=false;}}
$('research-form').addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);const f=new FormData(event.target),lat=f.get('lat'),lng=f.get('lng');if(Boolean(lat)!==Boolean(lng)){notice('위도와 경도를 함께 입력해주세요.',true);return;}pending={schema_version:'0.1',request_id:'web-'+crypto.randomUUID(),requested_at:new Date().toISOString(),store:{name:f.get('name').trim(),address:f.get('address').trim(),lat:lat?Number(lat):null,lng:lng?Number(lng):null},campaign:{purpose:f.get('purpose').trim(),product:f.get('product').trim(),target_hint:f.get('target_hint').trim()||null},research:{reference_date:f.get('reference_date'),radius_m:Number(f.get('radius_m')),lookback_days:Number(f.get('lookback_days'))}};activeJob=null;$('result').hidden=true;save();send();});
$('retry').addEventListener('click',()=>{if(pending)send();});$('resume').addEventListener('click',()=>{polls=0;poll();});
$('download').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([markdown],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='SPOT-research-brief.md';a.click();URL.revokeObjectURL(url);});
async function init(){try{const config=await api('/api/config');document.querySelector('[name=reference_date]').value=config.reference_date;const saved=JSON.parse(sessionStorage.getItem('spot-work')||'null');if(saved?.activeJob){pending=saved.pending;activeJob=saved.activeJob;$('submit').disabled=Boolean(pending);await poll();}else if(saved?.pending){pending=saved.pending;notice('접수 결과가 확인되지 않은 요청이 있어요. 같은 요청을 다시 연결할 수 있어요.');$('retry').hidden=false;}}catch{notice('화면을 준비하지 못했어요. 새로고침해주세요.',true);}}init();

}