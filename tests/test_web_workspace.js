const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.dataset={};this.events={};this.attributes={};this.hidden=false;this.style={};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(){this.children=[];}
  addEventListener(name,handler){this.events[name]=handler;}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
  showModal(){this.open=true;}
  close(){this.open=false;}
  querySelectorAll(tag){const nodes=[];const walk=node=>{if(node.tag===tag)nodes.push(node);for(const child of node.children||[])walk(child);};walk(this);return nodes;}
  set innerHTML(value){throw new Error('Unsafe HTML path');}
}
async function scenario(status){
  const ids=new Map(),names=['overview','quant','local','trend','brief','sources','history'];
  const get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id);};
  const views=names.map(name=>{const e=get('view-'+name);e.id='view-'+name;return e;});
  const nav=names.map(name=>{const e=new Element('button');e.dataset.view=name;return e;});
  const newButton=new Element('button'),date=new Element('input');
  const document={getElementById:get,createElement:tag=>new Element(tag),createTextNode:text=>({tag:'#text',textContent:text}),querySelector:()=>date,querySelectorAll:selector=>selector==='.view'?views:selector==='[data-new]'?[newButton]:nav};
  const storage=new Map([['spot-work',JSON.stringify({activeJob:'a'.repeat(32),pending:null,lastRequest:{store:{name:'범용 테스트 매장',address:'서울의 테스트 주소'},campaign:{product:'테스트 제품'}}})]]);
  const source={source_id:'S-Q-1',source_name:'Official <img>',source_url:'https://example.org/data'};
  const trendCard={type:'reference_case',event_name:'합성 축제 미션',observation:'미션 체험',sources:[source],why_relevant:['전체 분포를 읽은 응용 검토'],adaptation_hypotheses:[{statement:'같은 방문 흐름에서 기능 차이를 비교할 수 있을까?'}],audience_fit:[{population_kind:'floating_population',rationale:'유동·매출 최다 시간대는 각각의 관측입니다.',next_check:'도입 체험과 제품 가치 비교를 다른 상황에서 검토할 수 있을까? <script>'}]};
  const calls=[];
  const context={document,URL,Blob,console,FormData:class{constructor(form){this.form=form}get(name){return this.form[name]??''}},AbortSignal,crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout:()=>{},sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},fetch:async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>path==='/api/config'?{reference_date:'2026-10-02'}:{job_id:'a'.repeat(32),status,result:{module_status:{quant:'success',local:'partial',trend:'partial'},research_brief_markdown:'## 상권·인구\n| 지표 | 값 |\n|---|---|\n| 합성 | 0 |',research_brief:{source_count:1,overview:{area_summary:'합성 검증 데이터',primary_customer_signal:'관측 구성'},unique_local_signals:[{module:'quant',title:'합성 관측값',statement:'테스트',value:0,unit:'명',metric_refs:['daily_avg_floating_population'],sources:[source]}],local_changes:[],trend_patterns:[trendCard],research_review:{performed:true},why_here_now:'합성 판단'}}}};}};
  vm.runInNewContext(fs.readFileSync('src/web/static/app.js','utf8'),context);
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,2);assert(calls.every(([,options])=>!options?.method));
  assert.equal(date.value,'2026-10-02');
  assert.equal(get('context-label').textContent,'범용 테스트 매장 × 테스트 제품');
  newButton.events.click();assert.equal(get('request-dialog').open,true);get('close-request').events.click();assert.equal(get('request-dialog').open,false);
  if(status==='completed'){
    assert.equal(get('overview-content').hidden,false);
    assert.equal(get('quant-cards').className,'quant-dashboard');
    const card=get('quant-cards').children[0].children[0];assert(card.children[1].children[0].textContent==='0');
    card.children.at(-1).events.click();assert.equal(get('evidence-dialog').open,true);
    const links=get('evidence-sources').querySelectorAll('a');assert.equal(links[0].href,'https://example.org/data');assert.equal(links[0].textContent,'Official <img>');
    const trend=get('trend-cards').children[0];assert(trend.children.some(e=>e.textContent===trendCard.adaptation_hypotheses[0].statement));
    trend.children.at(-1).children.at(-1).events.click();
    const fit=get('evidence-meta').querySelectorAll('details')[0];
    assert.equal(fit.children[0].textContent,'유동인구 · 매장 응용 검토');
    assert.equal(fit.children[2].textContent,trendCard.audience_fit[0].next_check);
    nav.find(e=>e.dataset.view==='sources').events.click();assert.equal(get('view-overview').hidden,true);assert.equal(get('view-sources').hidden,false);
    nav.find(e=>e.dataset.view==='history').events.click();assert.equal(get('history-list').children.length,1);
    assert.equal(JSON.parse(storage.get('spot-work')).history[0].status,'completed');
    for(const question of ['', '어떤 사용 가치를 강조할까?']){
      get('research-form').events.submit({preventDefault(){},target:{product:'테스트 서비스',purpose:question,name:'테스트 매장',address:'부산 테스트 주소',lat:'35.2',lng:'129.08',reference_date:'2026-10-03',radius_m:'1000',lookback_days:'180'}});
      await new Promise(resolve=>setImmediate(resolve));
      const sent=JSON.parse(calls.filter(([path,options])=>path==='/api/research'&&options?.method==='POST').at(-1)[1].body);
      assert.equal(sent.campaign.product,'테스트 서비스');
      assert.equal(sent.campaign.purpose,question||'제품·지역 맥락을 연결한 홍보 근거 탐색');
    }
  }else{
    assert.equal(get('overview-content').hidden,true);
    assert.equal(get('job-state').textContent,'조사 진행 중');
    assert(!get('scout-cards').querySelectorAll('span').some(e=>e.textContent.includes('✓')));
    assert.equal(get('signal-cards').children.length,0);
  }
}
(async()=>{await scenario('completed');await scenario('running');console.log('Workspace navigation, source drawer, history, restore and honest progress passed.');})().catch(error=>{console.error(error);process.exitCode=1;});
