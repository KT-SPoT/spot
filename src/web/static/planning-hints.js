/* Presentation hints from the completed brief. No network or model calls. */
const SPOTPlanningHints = (() => {
  const labels={male:'남성',female:'여성',under_10:'10세 미만',teens:'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대', '60_plus':'60대 이상',mon:'월',tue:'화',wed:'수',thu:'목',fri:'금',sat:'토',sun:'일','05_09':'05~09시','09_12':'09~12시','12_14':'12~14시','14_18':'14~18시','18_23':'18~23시','23_05':'23~05시'};
  function safeUrl(raw){try{const u=new URL(raw);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
  function build(brief={},request={}){
    const quant=(brief.unique_local_signals||[]).filter(c=>c.module==='quant');
    const fields=['상권','타깃 고객','타깃 상품','행사 기간','직원 수','판촉물·예산'].map((label,i)=>({number:i+1,label,basis:[],hints:[],questions:[],sources:[]}));
    function add(field,card,text){field.basis.push(text);for(const source of card.sources||[]){const url=safeUrl(source.source_url);if(url&&!field.sources.some(s=>s.url===url))field.sources.push({url,title:source.title||source.source_name||'원본 근거'});}}
    for(const c of quant){
      const title=c.title||'공공 관측',period=`기준 ${c.reference_period||'별도 확인'} · ${c.scope||'집계 범위 별도 확인'}`;
      if(c.value!==undefined&&c.value!==null&&['최다 주요시설 유형','주거인구','직장인구'].includes(title))add(fields[0],c,`${title}: ${c.value}${c.unit||''} (${period})`);
      if(c.shares&&/성별|연령|요일|시간/.test(title)){
        const values=Object.entries(c.shares).filter(([k,v])=>k!=='total'&&typeof v?.share_pct==='number'&&Number.isFinite(v.share_pct)&&v.share_pct>=0&&v.share_pct<=100);
        const groups=/성별|연령/.test(title)?[values.filter(([k])=>['male','female'].includes(k)),values.filter(([k])=>['under_10','teens','20s','30s','40s','50s','60_plus'].includes(k))]:[values];
        const peaks=groups.flatMap(group=>{const peak=Math.max(...group.map(([,v])=>v.share_pct));return peak>0?group.filter(([,v])=>v.share_pct===peak).map(([k,v])=>`${labels[k]||k} ${v.share_pct}%`):[];});
        if(peaks.length)add(fields[/요일|시간/.test(title)?3:1],c,`${title}: ${peaks.join(' / ')} (${period})`);
      }
    }
    if(brief.overview?.area_summary&&!/정량 지표|자료 수|근거와 함께 요약/.test(brief.overview.area_summary))fields[0].basis.unshift(brief.overview.area_summary);
    const local=brief.local_changes||[];
    for(const c of local.slice(0,2))add(fields[0],c,`${c.title||'지역 변화'} · ${(c.published_at||'보도일 별도 확인').slice(0,10)}: ${c.evidence||c.statement||''}`);
    fields[0].questions=['매장 방문 동선에 실제로 연결되는 역·시설·생활권은 어디인가요?'];
    fields[1].hints=['인구 구성은 주변 상권의 관측입니다. 실제 매장 방문 고객 비중·상품 선호와 구분해 참고하세요. 성별과 연령은 각각의 비중이며 교차 비율이 아닙니다.'];
    fields[1].questions=['실제 방문 고객은 주로 주민·직장인·통행 고객 중 누구인가요?'];
    if(request.campaign?.product)fields[2].basis.push(`사용자가 지정한 상품: ${request.campaign.product}`);
    fields[2].questions=['홍보할 단말기·요금제·부가서비스와 강조할 가치는 무엇인가요?'];
    fields[2].hints=['성별·나이만으로 모델이나 요금제를 정하기보다, 방문자가 겪는 사용 장면과 공식 상품 기능을 연결해 선택하세요.'];
    fields[3].hints=['관측된 피크 요일·시간은 일정 선택의 참고입니다. 준비·행사·사후 처리에 필요한 시간은 따로 정하세요.'];
    fields[3].questions=['희망 날짜와 실제 운영 가능한 시간은 언제인가요?'];
    fields[4].questions=['일반 매장 업무를 제외하고 행사에 투입할 수 있는 직원은 몇 명인가요?','안내·체험 지원·상담을 동시에 맡을 수 있는지 확인했나요?'];
    fields[5].questions=['현재 보유한 판촉물과 구매·제작에 쓸 수 있는 예산은 얼마인가요?'];
    const cases=(brief.trend_patterns||[]).filter(c=>c.type==='reference_case');
    for(const c of cases){
      const observation=c.observation||'',mechanisms=new Set((c.adaptation_hypotheses||[]).map(h=>h.mechanism));
      if((observation.includes('□')||/브리핑/.test(c.event_name||''))&&observation.includes('...'))continue;
      const candidate=mechanisms.has('photo_sharing')&&/촬영|SNS|공유|유튜브/.test(observation)?'카메라 체험 결과물 카드':mechanisms.has('collectible_reward')&&/굿즈|수집|소장|기념품/.test(observation)?'기능 체험 완료 카드·작은 기념물':null;
      if(candidate&&!fields[5].hints.some(t=>t.startsWith(candidate))){fields[5].hints.push(`${candidate} — 체험 이후 결과물·기념물을 가져가는 접점 후보. 보유품과 구분하고 예산·제작 가능 여부를 확인하세요.`);add(fields[5],c,`${c.event_name||'전국 체험 사례'}: ${observation}`);}
      if(!candidate&&mechanisms.has('direct_product_trial')&&/체험|직접 사용|비교/.test(observation)&&fields[2].basis.length<2){add(fields[2],c,`${c.event_name||'직접 체험 사례'}: ${observation}`);const hint='사례의 참여 방식을 참고해, 선택한 상품의 기능을 직접 써보고 비교하는 사용 장면을 검토하세요.';if(!fields[2].hints.includes(hint))fields[2].hints.push(hint);}
    }
    const resident=quant.find(c=>c.title==='주거인구'),worker=quant.find(c=>c.title==='직장인구');
    const opportunities=[];
    if([resident,worker].every(c=>typeof c?.value==='number'&&Number.isFinite(c.value)&&c.value>0))opportunities.push({basis:'주거인구와 직장인구가 각각 관측된 상권',hint:'방문자가 생활용·업무용 사용 장면을 직접 고르게 하는 체험을 검토할 수 있어요. 두 모집단의 중복·비중이나 실제 고객 선호를 뜻하지 않습니다.'});
    return {title:'흥부장 작성 힌트',store:request.store?.name||'조사 매장',fields,opportunities};
  }
  function fieldText(f){return [`${f.number}. ${f.label}`, ...f.basis.map(t=>`조사 참고: ${t}`),...f.hints.map(t=>`선택 힌트: ${t}`),...f.questions.map(t=>`내가 정할 내용: ${t}`),...f.sources.map(s=>`근거: ${s.title} — ${s.url}`)].join('\n');}
  function text(model){return [model.title,model.store,'조사 결과를 참고해 각 항목을 직접 작성하세요. 힌트는 기획 제안이며 고객 호응·행사 효과를 입증하지 않습니다.',...model.fields.map(fieldText),...model.opportunities.map(o=>`숨은 기회 후보\n관측: ${o.basis}\n기획 힌트: ${o.hint}`)].join('\n\n')+'\n';}
  function render(doc,target,model){
    target.replaceChildren();target.hidden=false;
    const el=(tag,text,parent,cls)=>{const n=doc.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;parent.append(n);return n;};
    el('p','PLANNING NOTES',target,'eyebrow');el('h2',model.title,target);
    el('p','흥부장 양식의 여섯 항목을 채울 때 참고하세요. 조사 근거와 선택 질문을 읽고, 필요한 항목만 복사할 수 있습니다.',target,'planning-intro');
    const status=el('p','',target,'planning-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const grid=el('div','',target,'planning-grid');
    for(const f of model.fields){const card=el('article','',grid,'planning-card');el('span',String(f.number).padStart(2,'0'),card,'planning-number');el('h3',f.label,card);
      if(f.basis.length){el('h4','조사 참고',card);const list=el('ul','',card);for(const line of f.basis)el('li',line,list);}else el('p',f.number===5?'가용 인력은 매장에서 정할 내용입니다.':'이 항목의 직접 관측 자료가 충분하지 않아요. 아래 질문을 기준으로 정해주세요.',card,'muted');
      if(f.hints.length){el('h4','선택 힌트',card);for(const line of f.hints)el('p',line,card);}
      el('h4','내가 정할 내용',card);const qs=el('ul','',card,'planning-questions');for(const q of f.questions)el('li',q,qs);
      if(f.sources.length){const detail=el('details','',card);el('summary',`근거 ${f.sources.length}개 보기`,detail);for(const s of f.sources){const a=el('a',s.title,detail);a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';}}
      const copy=el('button','이 항목 힌트 복사',card,'text-button');copy.type='button';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(fieldText(f));status.textContent=`${f.label} 힌트를 복사했어요.`;}catch{status.textContent='자동 복사를 사용할 수 없어요. 아래 텍스트를 선택해 복사해주세요.';const area=el('textarea',fieldText(f),card);area.setAttribute('aria-label',`${f.label} 복사용 힌트`);area.readOnly=true;area.focus();area.select();}});
    }
    for(const o of model.opportunities){const box=el('aside','',target,'planning-opportunity');el('h3','숨은 기회 후보',box);el('p',o.basis,box,'muted');el('p',o.hint,box);}
    el('p','판촉물·체험 아이디어는 기획 제안입니다. 타깃 상품, 행사 일정, 인력과 예산은 사용자가 결정합니다.',target,'planning-footnote');
  }
  return {build,text,render,safeUrl};
})();
if(typeof module!=='undefined')module.exports=SPOTPlanningHints;
