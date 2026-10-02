const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(){this.children=[];this.events={};this.dataset={};this.attributes={};this.value='';this.textContent='';this.classList={add(){},toggle(){}};}
 append(...items){this.children.push(...items)} prepend(item){this.children.unshift(item)} replaceChildren(){this.children=[]}
 addEventListener(name,fn){this.events[name]=fn} setAttribute(name,value){this.attributes[name]=value} querySelector(){return null}
 set innerHTML(value){throw Error('HTML not allowed')}
}
const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)};
const context={document:{getElementById:get,querySelector:selector=>get(selector),querySelectorAll:()=>[],createElement:()=>new Element(),body:new Element()},URL,AbortSignal,setTimeout:fn=>fn(),fetch:()=>{throw Error('No provider call during report rendering')}};
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
console.log('Grounded summary, insight evidence, source filters, progress and empty results passed.');
