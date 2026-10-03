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
assert(walk(host).some(e=>e.tag==='iframe'&&e.src==='https://www.youtube-nocookie.com/embed/ABCDEFGHIJK'));
assert(walk(host).some(e=>e.tag==='img'&&e.src==='https://news.example/photo.jpg'));
const form=walk(host).find(e=>e.tag==='form'),input=walk(form).find(e=>e.tag==='input');input.value='https://instagram.com/p/ABcD123/';form.events.submit({preventDefault(){}});
assert(store.get('spot-media:one').includes('ABcD123'));assert.equal(JSON.stringify(brief),before);
board.render(doc,host,brief,{request_id:'two'},()=>{},{});assert(!walk(host).some(e=>e.href==='https://www.instagram.com/p/ABcD123/'));
board.render(doc,host,{},null,()=>{},{});assert(!walk(host).some(e=>e.tag==='iframe'));
console.log('Trend board media validation, thumbnails, evidence exclusion and request isolation passed.');
