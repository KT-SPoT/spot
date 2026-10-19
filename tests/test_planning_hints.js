const assert=require('node:assert/strict');
const hints=require('../src/web/static/planning-hints.js');
const brief={unique_local_signals:[
 {module:'quant',title:'유동인구 성별·연령 구성',shares:{male:{share_pct:50},female:{share_pct:50},'20s':{share_pct:35},'60_plus':{share_pct:20},invalid:{share_pct:NaN}}},
 {module:'quant',title:'유동인구 요일 비중',shares:{sat:{share_pct:22}}},
 {module:'quant',title:'유동인구 시간별 비중',shares:{'14_18':{share_pct:55}}},
 {module:'quant',title:'최다 주요시설 유형',value:'의료/복지'}],
 trend_patterns:[{type:'reference_case',event_name:'촬영 팝업',observation:'20대가 현장을 촬영하고 SNS로 공유한다.',adaptation_hypotheses:[{mechanism:'photo_sharing'}],sources:[{source_url:'https://example.org/event'}]}]};
const before=JSON.stringify(brief),model=hints.build(brief,{store:{name:'테스트 매장'},campaign:{product:'무시할 상품'}}),text=hints.text(model);
assert.equal(JSON.stringify(brief),before);assert.equal(model.fields.length,6);
assert.equal(model.fields[2].summary,'');assert.equal(model.fields[4].summary,'');
assert(text.includes('의료/복지가 주요 시설 유형인 상권'));
assert(text.includes('20대 35%'));assert(text.includes('남성 50% / 여성 50%'));
assert(text.includes('토요일 22%'));assert(text.includes('14~18시 55%'));
assert(text.includes('20대 언급 행사'));assert(text.includes('촬영·결과물 공유'));
assert(!/근거:|조사에서 발견한|https:|무시할 상품|4시간 행사/.test(text));
const changed=structuredClone(brief);changed.unique_local_signals[0].shares={'60_plus':{share_pct:65},'20s':{share_pct:20}};
const updated=hints.text(hints.build(changed));assert(updated.includes('60대 이상 65%'));assert.equal(hints.build(changed).fields[5].summary,'');assert(!updated.includes('20대 35%'));
changed.unique_local_signals.push({module:'quant',title:'매출 연령 비중',shares:{'20s':{share_pct:48},'60_plus':{share_pct:8}}});
assert(hints.build(changed).fields[1].summary.includes('매출액은 20대 48%'));
changed.trend_patterns[0].observation='굿즈를 판매하고 기념품을 제공한다.';
changed.trend_patterns[0].taxonomy_tags=['collectible_reward'];
assert.equal(hints.build(changed).fields[5].summary,'');
assert(hints.build().fields.every(f=>f.summary===''));
changed.trend_patterns[0].sources=[];assert.equal(hints.build(changed).fields[5].summary,'');
class Element{constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.listeners={};}append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}setAttribute(){}addEventListener(name,fn){this.listeners[name]=fn;}}
const doc={createElement:t=>new Element(t)},root=new Element('section');hints.render(doc,root,model);
const nodes=[];function walk(n){nodes.push(n);for(const c of n.children)walk(c);}walk(root);
assert.equal(nodes.filter(n=>n.tag==='article').length,6);assert.equal(nodes.filter(n=>n.tag==='button').length,4);assert.equal(nodes.filter(n=>n.tag==='details'||n.tag==='a').length,0);
let copied='';Object.defineProperty(global,'navigator',{value:{clipboard:{writeText:async t=>{copied=t;}}},configurable:true});
(async()=>{await nodes.find(n=>n.tag==='button').listeners.click();assert(copied.startsWith('1. 상권'));assert(!copied.includes('2. 타깃 고객'));console.log('Compact fields, separate distributions, blank product/staff and sourced event ideas passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
