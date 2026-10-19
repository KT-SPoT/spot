const assert=require('node:assert/strict');
const {SPOTQuantCharts:charts}=require('../src/web/static/app.js');
class Element{
  constructor(tag){this.tag=tag;this.children=[];this.events={};this.attributes={};this.dataset={};this.style={};this.textContent='';}
  append(...items){this.children.push(...items)} replaceChildren(){this.children=[]}
  setAttribute(k,v){this.attributes[k]=v} addEventListener(k,v){this.events[k]=v}
  set innerHTML(value){throw Error('Unsafe HTML')}
}
const doc={createElement:tag=>new Element(tag)},root=new Element('main');
const source={source_id:'q1',source_url:'https://public.example/data'};
const flow={module:'quant',title:'유동인구 성별·연령 구성',population_kind:'floating_population',shares:{male:{share_pct:52.7,count:527},female:{share_pct:47.3,count:473},'30s':{share_pct:0,count:0},'40s':{share_pct:19.4}},sources:[source],reference_period:null,scope:'선택 영역'};
const sales={module:'quant',type:'quant_distribution',population_kind:'sales',distribution_kind:'gender',shares:{male:{share_pct:40},female:{share_pct:60}},sources:[source],reference_period:'2026년 제공 표'};
const day={module:'quant',type:'quant_distribution',population_kind:'floating_population',distribution_kind:'day',shares:{mon:{share_pct:0},fri:{share_pct:25.3},weekday:{share_pct:70}},sources:[source]};
const peak={module:'quant',title:'유동인구 최다 시간대',metric_refs:['peak_floating_time_band'],value:'14~18시',sources:[source]};
const metric={module:'quant',title:'유동인구',metric_refs:['daily_avg_floating_population'],value:0,unit:'명',sources:[source]};
const input=[flow,sales,day,peak,metric],before=JSON.stringify(input);let opened;
charts.render(doc,root,input,(card,module)=>opened=[card,module]);
function all(){const list=[];const walk=n=>{list.push(n);for(const child of n.children)walk(child)};walk(root);return list}
function text(){return all().map(n=>n.textContent).join('\n')}
assert(text().includes('52.7%'));assert(text().includes('0%'));assert(text().includes('자료 기준 · 미확인'));
assert(text().includes('14~18시'));assert(!text().includes('70%'));
const donut=all().find(n=>n.className==='quant-donut');
assert(donut.style.background.includes('52.7%'));assert.equal(donut.attributes['aria-label'],'남성 52.7%, 여성 47.3%');
assert(all().some(n=>n.className==='quant-column-fill'&&n.style.height==='0%'));
assert(text().includes('미확보를 0%로 처리'));
assert.equal(charts.rows(flow,'age','floating_population').length,6);
assert.equal(charts.rows(flow,'age','worker_population').length,5);
assert.equal(charts.rows(flow,'age','resident_population').length,7);
all().find(n=>n.tag==='button'&&n.textContent==='출처 · 근거 보기 ↗').events.click();assert.deepEqual(opened,[flow,'quant']);
all().find(n=>n.tag==='button'&&n.dataset.kind==='sales').events.click();
assert(text().includes('매출액의 구성비'));assert(text().includes('60%'));assert(!text().includes('52.7%'));assert(text().includes('2026년 제공 표'));
all().find(n=>n.tag==='button'&&n.dataset.kind==='resident_population').events.click();assert(!text().includes('시간대별 비중'));assert(text().includes('제공 비율 미확보'));
assert.equal(JSON.stringify(input),before);
// Incomplete and non-100% gender shares must not be converted into a full ring.
for(const shares of [{male:{share_pct:52.7}},{male:{share_pct:60},female:{share_pct:60}}]){
  charts.render(doc,root,[{...flow,shares}],()=>{});
  assert(!all().some(n=>n.className==='quant-donut'));
  assert(all().some(n=>n.className==='quant-bar-fill'&&n.style.width===String(shares.male.share_pct)+'%'));
}
charts.render(doc,root,[{...flow,type:'quant_distribution',distribution_kind:'time',shares:{'05_09':{share_pct:0},'18_23':{share_pct:26.2}}}],()=>{});
assert(text().includes('26.2%'));assert(text().includes('0%'));assert(all().some(n=>n.className?.includes('quant-time-cell is-missing')));
for(const invalid of [NaN,Infinity,-1,101,true,'40'])assert.equal(charts.rows({...flow,shares:{male:{share_pct:invalid}}},'gender','floating_population')[0].value,null);
charts.render(doc,root,[{...flow,sources:[]}],()=>{});assert(!text().includes('52.7%'));
charts.render(doc,root,[],()=>{});assert(text().includes('확보하지 못'));
console.log('Quant charts: exact/zero/missing percentages, population tabs, provenance, safe DOM and unmodified evidence passed.');
