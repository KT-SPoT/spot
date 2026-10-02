const assert = require('node:assert/strict');
const {renderBrief} = require('../src/web/static/app.js');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(){this.children=[];}
}
const doc={createElement:tag=>new Element(tag),createTextNode:text=>({tag:'#text',textContent:text})};
const root=new Element('root');
const input='# SPOT\n- 요청: internal-id\n## 상권·인구 지표\n| 이름 | 값 |\n|---|---:|\n| 관측 | 20 |\n## 출처\n- [공식](https://example.org/evidence)\n- [악성](javascript:alert(1))\n- <img src=x onerror=alert(1)>\n- [계정](https://user:password@example.org/)';
renderBrief(doc,root,input);
const nodes=[];function walk(node){nodes.push(node);for(const child of node.children||[])walk(child);}walk(root);
assert.equal(nodes.filter(node=>node.tag==='details').length,2);
assert.equal(nodes.filter(node=>node.tag==='table').length,1);
assert.equal(nodes.filter(node=>node.tag==='td').length,2);
const links=nodes.filter(node=>node.tag==='a');assert.equal(links.length,1);
assert.equal(links[0].href,'https://example.org/evidence');assert.equal(links[0].rel,'noopener noreferrer');
assert(!nodes.some(node=>node.tag==='img'||node.tag==='script'));
assert(nodes.some(node=>node.textContent.includes('<img')));
assert(!nodes.some(node=>node.textContent.includes('internal-id')));
console.log('Brief tables, sections, safe links and literal HTML rendering passed.');
