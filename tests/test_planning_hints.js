const assert=require('node:assert/strict');
const hints=require('../src/web/static/planning-hints.js');
const brief={unique_local_signals:[
  {module:'quant',title:'유동인구 성별·연령 구성',shares:{male:{share_pct:50},female:{share_pct:50},'20s':{share_pct:35},'30s':{share_pct:20},invalid:{share_pct:NaN}},reference_period:'2026-08',scope:'선택영역',sources:[{source_url:'https://public.example/data',title:'공공 자료'},{source_url:'javascript:alert(1)'},{source_url:'https://user:password@example.org'}]},
  {module:'quant',title:'유동인구 시간별 비중',shares:{'14_18':{share_pct:55}}},
  {module:'quant',title:'주거인구',value:100},{module:'quant',title:'직장인구',value:90}],
  trend_patterns:[{type:'reference_case',event_name:'촬영 체험',observation:'현장 체험을 촬영하고 공유',adaptation_hypotheses:[{mechanism:'photo_sharing'}],sources:[{source_url:'https://news.example/a',title:'촬영 보도'}]}]};
const before=JSON.stringify(brief),model=hints.build(brief,{store:{name:'테스트 매장'}}),text=hints.text(model);
assert.equal(model.fields.length,6);assert.equal(JSON.stringify(brief),before);
assert(text.includes('남성 50% / 여성 50%'));assert(text.includes('2026-08 · 선택영역'));
assert(text.includes('20대 35%'));assert(text.includes('교차 비율이 아닙니다'));
assert(text.includes('14~18시 55%'));assert(text.includes('필요한 시간은 따로 정'));
assert(!text.includes('4시간 행사'));assert(!text.includes('기획해주세요'));assert(!text.includes('password'));assert(!text.includes('javascript:'));
assert(text.includes('카메라 체험 결과물 카드'));assert(text.includes('보유품과 구분'));assert.equal(model.opportunities.length,1);
assert.equal(hints.build({unique_local_signals:[{module:'quant',title:'주거인구',value:true},{module:'quant',title:'직장인구',value:90}]}).opportunities.length,0);
assert.equal(model.fields[4].basis.length,0);assert.equal(hints.build().fields[2].basis.length,0);
class Element{constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.listeners={};}append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}setAttribute(){}addEventListener(name,fn){this.listeners[name]=fn;}}
const doc={createElement:t=>new Element(t)},root=new Element('section');hints.render(doc,root,model);
const nodes=[];function walk(n){nodes.push(n);for(const c of n.children)walk(c);}walk(root);
assert.equal(nodes.filter(n=>n.tag==='article').length,6);assert.equal(nodes.filter(n=>n.tag==='button').length,6);
assert(nodes.filter(n=>n.tag==='a').every(n=>n.rel==='noopener noreferrer'));
let copied='';Object.defineProperty(global,'navigator',{value:{clipboard:{writeText:async t=>{copied=t;}}},configurable:true});
(async()=>{await nodes.find(n=>n.tag==='button').listeners.click();assert(copied.startsWith('1. 상권'));assert(!copied.includes('2. 타깃 고객'));console.log('Six-field hints, valid observations, safe sources, unknown inputs and per-field copy passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
