const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.events={};this.attributes={};this.textContent='';}
 append(...c){this.children.push(...c)} replaceChildren(){this.children=[]} setAttribute(k,v){this.attributes[k]=v}
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
const form=walk(host).find(e=>e.tag==='form'),input=walk(form).find(e=>e.tag==='input');input.value='https://instagram.com/p/ABcD123/';form.events.submit({preventDefault(){}});
assert(store.get('spot-media:one').includes('ABcD123'));assert.equal(JSON.stringify(brief),before);
board.render(doc,host,brief,{request_id:'two'},()=>{},{});assert(!walk(host).some(e=>e.href==='https://www.instagram.com/p/ABcD123/'));
board.render(doc,host,{},null,()=>{},{});assert(!walk(host).some(e=>e.tag==='iframe'));
const discovery={video_sources:[{source_url:'https://youtu.be/12345678901',title:'브리프에 채택되지 않은 참고 영상'}, {source_url:'https://youtube.com.evil.org/watch?v=ABCDEFGHIJK',title:'거절할 URL'}]};
assert.equal(board.collectVideos(brief,discovery).length,2);
board.render(doc,host,{trend_patterns:[{type:'reference_case',event_name:'기사 사례',observation:'사례 관측',sources:[{source_url:'https://news.example/a',title:'기사'}]}]},null,()=>{},discovery);
assert(walk(host).some(e=>e.textContent.includes('선택한 뉴스 사례의 관련 영상이라는 의미는 아닙니다')));
assert(!walk(walk(host).find(e=>e.className==='trend-news trend-selected-case')).some(e=>e.className==='trend-video-cover'));
assert(walk(host).some(e=>e.src==='https://i.ytimg.com/vi/12345678901/hqdefault.jpg'));
assert(!walk(host).some(e=>e.tag==='iframe'));
const caseBrief={trend_patterns:[{type:'reference_case',case_id:'a',event_name:'기사 A',sources:[{source_url:'https://news.example/a',title:'기사 A'}]},{type:'reference_case',case_id:'b',event_name:'기사 B',sources:[{source_url:'https://news.example/b',title:'기사 B'}]}]};
board.render(doc,host,caseBrief,{request_id:'independent'},()=>{},discovery);
const videoSection=walk(host).find(e=>e.className==='trend-video-reference');
walk(videoSection).find(e=>e.className==='trend-video-cover').events.click();
walk(host).find(e=>e.className==='trend-case-nav').children[1].events.click();
assert(walk(host).some(e=>e.className==='trend-case-title'&&e.textContent==='기사 B'));
assert(walk(host).includes(videoSection));
assert(walk(videoSection).some(e=>e.tag==='iframe')); // Case selection must not replace independent playback.
board.render(doc,host,{},null,()=>{},discovery);assert(walk(host).some(e=>e.className==='trend-video-cover'));
board.renderOverview(doc,host,{},discovery);assert.equal(host.hidden,false);
board.renderOverview(doc,host,{},{});assert.equal(host.hidden,true);assert.equal(host.children.length,0);
console.log('Trend board media validation, thumbnails, evidence exclusion and request isolation passed.');
(async()=>{
 board.render(doc,host,brief,{request_id:'api'},()=>{},{});
 const forms=walk(host).filter(e=>e.tag==='form'),search=forms[1];
 const query=walk(search).find(e=>e.tag==='input');query.value='행사';
 ctx.fetch=async(url,options)=>{assert.equal(url,'/api/instagram/search');assert.equal(JSON.parse(options.body).hashtag,'행사');return {ok:false,json:async()=>({error:{code:'INSTAGRAM_PERMISSION_REQUIRED'}})};};
 await search.events.submit({preventDefault(){}});
 assert(walk(host).some(e=>e.textContent.includes('공개 해시태그 검색 권한이 부족')));
 ctx.fetch=async()=>({ok:true,json:async()=>({hashtag:'행사',collected_at:'2026-10-04',items:[{url:'https://instagram.com/p/RESULT123/','caption':'<script>untrusted</script>'}]})});
 await search.events.submit({preventDefault(){}});
 assert(walk(host).some(e=>e.textContent==='<script>untrusted</script>'));
 assert(walk(host).some(e=>e.href==='https://www.instagram.com/p/RESULT123/'));
 assert.equal(JSON.stringify(brief),before);
 console.log('Instagram lookup permission feedback, safe captions and evidence exclusion passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
