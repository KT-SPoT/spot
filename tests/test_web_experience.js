const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(){this.children=[];this.events={};this.dataset={};this.attributes={};this.style={};this.value='';this.textContent='';this.classList={add(){},toggle(){}};}
 append(...items){this.children.push(...items)} prepend(item){this.children.unshift(item)} replaceChildren(){this.children=[]}
 addEventListener(name,fn){this.events[name]=fn} setAttribute(name,value){this.attributes[name]=value} querySelector(){return null}
 set innerHTML(value){throw Error('HTML not allowed')}
}
const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)};
const context={document:{getElementById:get,querySelector:selector=>get(selector),querySelectorAll:()=>[],createElement:()=>new Element(),body:new Element()},SPOTQuantCharts:require('../src/web/static/app.js').SPOTQuantCharts,URL,AbortSignal,setTimeout:fn=>fn(),fetch:()=>{throw Error('No provider call during report rendering')}};
vm.createContext(context);vm.runInContext(fs.readFileSync('src/web/static/experience.js','utf8')+'\nthis.experience=SPOTExperience;',context);
const source={source_id:'s1',source_url:'https://public.go.kr/data',source_name:'공공데이터'};
const brief={unique_local_signals:[{module:'quant',title:'유동인구 주요 성별',value:'여성',statement:'여성 비중 53%',sources:[source]}],local_changes:[{title:'도서관 개관 예정',evidence:'개관이 예정되어 있다',sources:[{source_id:'l1',source_url:'https://news.example/story',source_type:'news'}]}],trend_patterns:[]};
let rows=[],clicked;context.experience.display(brief,null,(s,target)=>{rows.push(s);target.append(new Element())},card=>clicked=card);
assert(get('area-summary').textContent.includes('도서관 개관 예정'));assert(!get('area-summary').textContent.includes('변화가 확인'));
assert(get('key-insights').children[0].children[1].textContent.includes('여성'));
get('key-insights').children[1].events.click();assert.equal(clicked.title,'도서관 개관 예정');
const library=get('source-list'),tabs=library.children[0];assert.equal(tabs.children.length,5);
rows=[];tabs.children.find(button=>button.dataset.category==='공공데이터').events.click();assert.deepEqual(rows,[source]);
context.experience.progress('running',{quant:'success',local:'running'});assert.equal(get('research-steps').children[1].attributes['aria-current'],'step');
context.experience.display({},null,()=>{},()=>{});assert(get('area-summary').textContent.includes('충분하지'));
const failure='소상공인365 서버가 일시적으로 응답하지 않습니다(HTTP 503). 잠시 후 새 조사를 시작해주세요.';
context.experience.display({needs_manual_check:['quant: '+failure]},null,()=>{},()=>{});
assert.equal(get('quant-cards').children[0].textContent,failure);
const metric=new Element();metric.textContent='공공 관측 지표';get('quant-cards').replaceChildren();get('quant-cards').append(metric);
context.experience.display({unique_local_signals:brief.unique_local_signals,needs_manual_check:['quant: 일부 자료 없음']},null,()=>{},()=>{});
assert.equal(get('quant-cards').children[0],metric); // Existing metric cards must not be replaced.
const zero={module:'quant',title:'유동인구',metric_refs:['daily_avg_floating_population'],value:0,sources:[source]};
const age={module:'quant',title:'연령 구성',population_kind:'floating_population',distribution_kind:'age',shares:{'40s':{share_pct:0}},sources:[source]};
context.experience.display({unique_local_signals:[zero,age],local_changes:[],trend_patterns:[{type:'reference_case',event_name:'연결 후보',sources:[source]}]},null,()=>{},()=>{});
const descendants=root=>{const nodes=[root];for(const child of root.children)nodes.push(...descendants(child));return nodes};
context.experience.display({local_changes:[{module:'local',title:'기사 이미지',sources:[{...source,verification:{thumbnail_url:'https://example.org/article.jpg'}}]}]},null,()=>{},()=>{});
assert(descendants(get('overview-local')).some(node=>node.src==='https://example.org/article.jpg'));
context.experience.display({unique_local_signals:[zero,age],local_changes:[],trend_patterns:[{type:'reference_case',event_name:'연결 후보',sources:[source]}]},null,()=>{},()=>{});
assert(descendants(get('overview-metrics')).some(node=>node.textContent==='0명'));
assert(descendants(get('overview-population')).some(node=>node.textContent.includes('40대 0%')));
assert.equal(get('overview-trend').children.length,1);assert.equal(get('overview-local').children[0].textContent,'지역 변화 근거를 확보하지 못했어요.');
context.experience.display({},null,()=>{},()=>{});
assert(!descendants(get('overview-metrics')).some(node=>node.textContent==='0명')); // Clear prior run metrics.
assert.equal(get('area-map-caption').textContent,'좌표가 확보된 요청에 조사 위치와 반경을 표시합니다.');
console.log('Grounded summary, insight evidence, source filters, progress and empty results passed.');
