const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.events={};this.attributes={};this.textContent='';}
 append(...c){for(const child of c){child.attached=true;if(child.tag==='iframe')assert.equal(child.referrerPolicy,'strict-origin-when-cross-origin','Configure player identification before attaching iframe');}this.children.push(...c)} replaceChildren(){this.children=[]} setAttribute(k,v){this.attributes[k]=v}
 set src(value){if(this.tag==='iframe'){assert(!this.attached,'Set video URL before inserting iframe');assert.equal(this.referrerPolicy,'strict-origin-when-cross-origin','First navigation must preserve origin');}this._src=value} get src(){return this._src}
 insertBefore(e,ref){this.children=this.children.filter(c=>c!==e);this.children.splice(this.children.indexOf(ref),0,e)}
 addEventListener(k,v){this.events[k]=v} set innerHTML(v){throw Error('No HTML injection')}
}
const doc={createElement:t=>new Element(t),getElementById:()=>null,body:new Element('body')};
const store=new Map();const ctx={document:doc,window:{},URL,sessionStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('src/web/static/trend-board.js','utf8')+'\nthis.board=SPOTTrendBoard',ctx);
const board=ctx.board;
assert.equal(board.instagramURL('https://www.instagram.com/reel/ABcD_123/?igsh=tracking'),'https://www.instagram.com/reel/ABcD_123/');
for(const url of ['https://instagram.com.evil.org/p/ABcD123/','javascript:alert(1)','https://user:secret@instagram.com/p/ABcD123/','https://instagram.com/stories/name/123/'])assert.equal(board.instagramURL(url),null);
assert.equal(board.youtubeID('https://youtu.be/ABCDEFGHIJK'),'ABCDEFGHIJK');assert.equal(board.youtubeID('https://youtube.com.evil.org/watch?v=ABCDEFGHIJK'),null);
const host=new Element('div'),brief={source_count:2,trend_patterns:[{type:'reference_case',case_id:'case-1',event_name:'실제 수집 자료 재생',sources:[{source_url:'https://www.youtube.com/watch?v=ABCDEFGHIJK',title:'영상'}, {source_url:'https://news.example/a',title:'기사',verification:{thumbnail_url:'https://news.example/photo.jpg'}}]}]};
const before=JSON.stringify(brief);const walk=e=>[e,...e.children.flatMap(walk)];
board.render(doc,host,brief,{request_id:'one'},()=>{},{});
assert(!walk(host).some(e=>e.tag==='iframe')); // Third-party playback starts only on click.
walk(host).find(e=>e.className==='trend-video-cover').events.click();
assert(walk(host).some(e=>e.tag==='iframe'&&e.src==='https://www.youtube-nocookie.com/embed/ABCDEFGHIJK?autoplay=1'));
assert(walk(host).some(e=>e.tag==='img'&&e.src==='https://news.example/photo.jpg'));
assert.equal(JSON.stringify(brief),before);assert(!walk(host).some(e=>e.tag==='form'||e.textContent==='Instagram · 시각 참고 추가'));
board.render(doc,host,{},null,()=>{},{});assert(!walk(host).some(e=>e.tag==='iframe'));
const discovery={video_sources:[{source_url:'https://youtu.be/12345678901',title:'브리프에 채택되지 않은 참고 영상'}, {source_url:'https://youtube.com.evil.org/watch?v=ABCDEFGHIJK',title:'거절할 URL'}]};
assert.equal(board.collectVideos(brief,discovery).length,2);
board.render(doc,host,{trend_patterns:[{type:'reference_case',event_name:'기사 사례',observation:'사례 관측',sources:[{source_url:'https://news.example/a',title:'기사'}]}]},null,()=>{},discovery);
assert(walk(host).some(e=>e.textContent.includes('뉴스 사례와 별도로 살펴볼 자료입니다')));
assert(!walk(walk(host).find(e=>e.className==='trend-news trend-selected-case')).some(e=>e.className==='trend-video-cover'));
assert(walk(host).some(e=>e.src==='https://i.ytimg.com/vi/12345678901/hqdefault.jpg'));
assert(!walk(host).some(e=>e.tag==='iframe'));
const caseBrief={trend_patterns:[{type:'reference_case',case_id:'a',event_name:'기사 A',sources:[{source_url:'https://news.example/a',title:'기사 A'}]},{type:'reference_case',case_id:'b',event_name:'기사 B',sources:[{source_url:'https://news.example/b',title:'기사 B'}]}]};
board.render(doc,host,caseBrief,{request_id:'independent'},()=>{},discovery);
const videoSection=walk(host).find(e=>e.className==='trend-video-reference');
assert(host.children.indexOf(videoSection)<host.children.findIndex(e=>e.className==='trend-case-nav'));
walk(videoSection).find(e=>e.className==='trend-video-cover').events.click();
walk(host).find(e=>e.className==='trend-case-nav').children[1].events.click();
assert(walk(host).some(e=>e.className==='trend-case-title'&&e.textContent==='기사 B'));
assert(walk(host).includes(videoSection));
assert(walk(videoSection).some(e=>e.tag==='iframe')); // Case selection must not replace independent playback.
board.render(doc,host,{},null,()=>{},discovery);assert(walk(host).some(e=>e.className==='trend-video-cover'));
board.renderOverview(doc,host,{},discovery);assert.equal(host.hidden,false);
board.renderOverview(doc,host,{},{});assert.equal(host.hidden,false);assert(host.children.length>0);
console.log('Trend board media validation, thumbnails, evidence exclusion and request isolation passed.');
const profiles=age=>({unique_local_signals:[{module:'quant',population_kind:'sales',distribution_kind:'age',shares:{[age]:{share_pct:50}},sources:[{source_url:'https://public.example/data'}]}],trend_patterns:[
 {type:'reference_case',case_id:'old',event_name:'60대 문화 팝업',observation:'60대 대상 행사',sources:[]},
 {type:'reference_case',case_id:'young',event_name:'20대 체험 팝업',observation:'20대 대상 행사',sources:[]}]});
assert.equal(board.orderCases(profiles('20s'))[0].case_id,'old'); // Age word overlap alone never promotes a case.
assert.equal(board.orderCases(profiles('60_plus'))[0].case_id,'old');
const connected=profiles('20s');connected.unique_local_signals.push({module:'quant',population_kind:'sales',distribution_kind:'time',sources:[{source_id:'S-Q-time'}]});connected.trend_patterns[1].adaptation_hypotheses=[{statement:'지역 관측: 저녁 시간 매출 48%. 사례에서 참고할 행동: 촬영 결과를 공유하는 방식. 연결 단서: 이 시간대의 기능 비교 체험을 검토합니다.',context_source_refs:[{module:'quant',source_id:'S-Q-time'}]}];
let opened;board.render(doc,host,connected,{request_id:'visible-reasons'},c=>opened=c,{});
const reasons=walk(host).find(e=>e.className==='trend-selection-reasons');assert.equal(reasons.tag,'section');
assert(walk(reasons).some(e=>e.textContent.includes('이 시간대의 기능 비교 체험')));
walk(reasons).find(e=>e.tag==='button').events.click();assert.equal(opened.case_id,'young');
assert(walk(host).some(e=>e.textContent==='저녁 시간 매출 48%.'));
connected.research_review={case_reviews:[{case_id:'young',verdict:'generic',reason:'근거 미확보 진단'}]};
board.render(doc,host,connected,null,()=>{},{});
assert(!walk(host).some(e=>e.className==='trend-application'||e.textContent.includes('미확보')));
assert(walk(host).some(e=>e.className==='trend-case-nav'));
assert(walk(host).some(e=>e.className==='trend-video-reference'));
connected.research_review.case_reviews[0].dimensions={local_customer_fit:'weak',transfer_logic:'clear',differentiation:'generic',overclaim:'clear'};
board.render(doc,host,connected,null,()=>{},{});
assert(walk(host).some(e=>e.className==='trend-application'));
assert(walk(host).some(e=>e.textContent==='BASIC CONNECTION / 기본 기획 참고'));
assert(!walk(host).some(e=>e.textContent.includes('미확보')));
connected.research_review.case_reviews[0].dimensions.overclaim='risk';
board.render(doc,host,connected,null,()=>{},{});
assert(!walk(host).some(e=>e.className==='trend-application'));
const ageConnection=profiles('20s');ageConnection.unique_local_signals[0].sources[0].source_id='S-Q-age';
ageConnection.trend_patterns[1].adaptation_hypotheses=[{kind:'research_question',synthesis_review:'coherent',contribution:'baseline',
 statement:'지역 관측: 업종 매출액의 주요 연령 구간. 사례에서 참고할 행동: 직접 비교한 방식. 연결 단서: 실제 사용 과제를 비교할까요?',context_source_refs:[{module:'quant',source_id:'S-Q-age'}]}];
board.render(doc,host,ageConnection,null,()=>{},{});
assert(walk(host).some(e=>e.className==='trend-application'));
assert(walk(host).some(e=>e.textContent==='BASIC CONNECTION / 기본 기획 참고'));
ageConnection.trend_patterns[1].adaptation_hypotheses[0].synthesis_review='weak';
board.render(doc,host,ageConnection,null,()=>{},{});
assert(!walk(host).some(e=>e.className==='trend-application'));
board.render(doc,host,{},null,()=>{},{video_status:'rate_limited'});
assert(walk(host).some(e=>e.textContent.includes('YouTube 검색 요청이 잠시 제한')));
assert(!walk(host).some(e=>e.tag==='form'||e.className==='trend-social'));
console.log('Audience-aware case order, visible context and reasons, Instagram section removal passed.');
