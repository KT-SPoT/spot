/* Presentation hints from the completed brief. No network or model calls. */
const SPOTPlanningHints = (() => {
  const labels={male:'남성',female:'여성',under_10:'10세 미만',teens:'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대', '60_plus':'60대 이상',mon:'월',tue:'화',wed:'수',thu:'목',fri:'금',sat:'토',sun:'일','05_09':'05~09시','09_12':'09~12시','12_14':'12~14시','14_18':'14~18시','18_23':'18~23시','23_05':'23~05시'};
  function safeUrl(raw){try{const u=new URL(raw);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
  function build(brief={},request={}){
    const quant=(brief.unique_local_signals||[]).filter(c=>c.module==='quant');
    const fields=['상권','타깃 고객','타깃 상품','행사 기간','직원 수','판촉물·예산'].map((label,i)=>({number:i+1,label,basis:[],hints:[],sources:[],note:''}));
    const valid=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100;
    const peaks=(c,keys)=>{const items=Object.entries(c.shares||{}).filter(([k,v])=>k!=='total'&&(!keys||keys.includes(k))&&valid(v?.share_pct));const max=Math.max(...items.map(([,v])=>v.share_pct));return max>0?items.filter(([,v])=>v.share_pct===max).map(([key,v])=>({key,value:v.share_pct,label:labels[key]||key})):[];};
    const peakText=items=>items.map(p=>`${p.label} ${p.value}%`).join(' / ');
    function add(field,card,text){if(!field.basis.includes(text))field.basis.push(text);for(const source of card.sources||[]){const url=safeUrl(source.source_url);if(url&&!field.sources.some(s=>s.url===url))field.sources.push({url,title:source.title||source.source_name||'원본 근거'});}}
    const hint=(i,text)=>{if(!fields[i].hints.includes(text))fields[i].hints.push(text);};
    for(const c of quant){
      const title=c.title||'공공 관측',period=`기준 ${c.reference_period||'별도 확인'} · ${c.scope||'집계 범위 별도 확인'}`;
      if(c.value!==undefined&&c.value!==null&&['최다 주요시설 유형','주거인구','직장인구'].includes(title))add(fields[0],c,`${title}: ${c.value}${c.unit||''} (${period})`);
      if(title==='최다 주요시설 유형'&&c.value){const facility=String(c.value);const scene=/의료|복지/.test(facility)?'시설 방문 전후에 참여하는 짧은 사진 촬영·정리 체험':/교육|학교/.test(facility)?'학교생활 사진·영상 제작 체험':/교통|역/.test(facility)?'이동 중 지도·길찾기 기능 체험':/시장|쇼핑|상업/.test(facility)?'장보기 동선의 스마트폰 결제 기능 체험':null;if(scene)hint(0,`주요 시설 유형 ‘${facility}’ → ${scene}이라는 생활권 접점 후보.`);}
      if(c.shares&&/성별|연령|요일|시간/.test(title)){
        const gender=peaks(c,['male','female']),age=peaks(c,['under_10','teens','20s','30s','40s','50s','60_plus']);
        const items=/성별|연령/.test(title)?[...gender,...age]:peaks(c);
        const idx=/요일|시간/.test(title)?3:1;
        if(items.length)add(fields[idx],c,`${title}: ${peakText(items)} (${period})`);
        const population=title.replace(/ 성별.*| 연령.*/,'');
        if(age.length)hint(1,`${population}에서 ${peakText(age)}가 최다 연령 구간 — ${age.map(p=>p.label).join('·')} 고객군을 이 상권의 타깃 후보로 연결할 단서.`);
        const male=c.shares.male?.share_pct,female=c.shares.female?.share_pct;
        if(valid(male)&&valid(female)&&male+female>0&&Math.abs(male-female)<=10)hint(1,`${population} 남성 ${male}%·여성 ${female}% — 성별 격차가 ${Math.abs(male-female).toFixed(1)}%p인 관측. 특정 성별보다 사용 장면을 앞세운 홍보 구성의 단서.`);
        if(idx===3&&items.length){const contact=/매출/.test(title)?'상담·구매 접점':'매장 발견·체험 접점';hint(3,`${title}의 최다 구간은 ${peakText(items)} — ${items.map(p=>p.label+(/요일/.test(title)?'요일':'')).join('·')} ${contact}의 운영 후보.`);}
      }
    }
    for(const c of (brief.local_changes||[]).slice(0,2)){
      const fact=c.evidence||c.statement||'',name=c.title||'지역 변화';add(fields[0],c,`${name} · ${(c.published_at||'보도일 별도 확인').slice(0,10)}: ${fact}`);
      if(/통행.*재개|개통|교통/.test(fact))hint(0,`‘${name}’의 이동·통행 변화 → 매장 오는 길·길찾기를 소재로 한 안내 콘텐츠 후보.`);
      else if(/개관|개점|신설/.test(fact))hint(0,`‘${name}’의 시설 변화 — 새 시설 이용 목적과 매장 노출 접점을 연결할 지역 단서.`);
      else if(/입주|주거|아파트/.test(fact))hint(0,`‘${name}’의 주거 변화 — 생활권 변화를 연결할 지역 단서. 보도된 사업 단계가 현재 고객 증가와 같지는 않음.`);
    }
    if(request.campaign?.product)fields[2].basis.push(`사용자가 지정한 상품: ${request.campaign.product}`);
    for(const c of (brief.trend_patterns||[]).filter(c=>c.type==='reference_case')){
      const observation=c.observation||'',name=c.event_name||'전국 체험 사례',mechanisms=new Set((c.adaptation_hypotheses||[]).map(h=>h.mechanism));
      if((observation.includes('□')||/브리핑/.test(name))&&observation.includes('...'))continue;
      if(mechanisms.has('photo_sharing')&&/촬영|SNS|공유|유튜브/.test(observation)){
        add(fields[2],c,`${name}: ${observation}`);hint(2,`‘${name}’의 촬영·공유 방식 → 카메라·영상 기능을 직접 체험하는 상품 접점 후보. 특정 모델 선호에 대한 조사는 아님.`);
        add(fields[5],c,`${name}: ${observation}`);hint(5,`‘${name}’의 촬영·공유 접점 → 카메라 체험 결과물 카드·사진 인화물이라는 판촉물 후보. 체험 결과가 가져갈 물건으로 이어지는 구성.`);
      }else if(mechanisms.has('collectible_reward')&&/굿즈|수집|소장|기념품/.test(observation)){
        add(fields[5],c,`${name}: ${observation}`);hint(5,`‘${name}’의 굿즈·소장 접점 → 기능 체험 완료 카드·소장용 스티커·작은 기념물이라는 판촉물 후보. 체험 결과와 기념물을 함께 남기는 구성.`);
      }else if(mechanisms.has('direct_product_trial')&&/체험|직접 사용|비교/.test(observation)){
        add(fields[2],c,`${name}: ${observation}`);hint(2,`‘${name}’의 직접 체험 방식 → ${/게임/.test(name+' '+observation)?'스마트폰 게임 실행·반응 비교':'스마트폰 기능을 직접 써보는 비교 체험'}라는 상품 접점 후보. 해당 상품의 효과·선호를 입증한 자료는 아님.`);
      }
    }
    fields[1].note='성별·연령은 각각의 구성비이며 교차 비율이 아님. 유동·주거·직장 인구와 매출은 서로 다른 집계. 실제 방문 고객 비중·상품 선호와 다름.';
    fields[3].note='요일·시간대는 각각의 집계이며 교차 집계가 아님. 행사 소요 시간에 대한 관측은 아님.';
    fields[2].note='모델별 고객 선호·가격대·공식 상품 사양은 이번 리서치에 없음.';
    fields[4].note='가용 직원 수·업무 배치에 관한 조사 데이터 없음.';
    fields[5].note='판촉물 후보는 조사 사례에서 연결한 아이디어. 보유품·제작비·예산 데이터 없음.';
    const resident=quant.find(c=>c.title==='주거인구'),worker=quant.find(c=>c.title==='직장인구');
    const opportunities=[];
    if([resident,worker].every(c=>typeof c?.value==='number'&&Number.isFinite(c.value)&&c.value>0))opportunities.push({basis:`주거인구 ${resident.value}${resident.unit||'명'} (${resident.reference_period||'기준 별도 확인'}) / 직장인구 ${worker.value}${worker.unit||'명'} (${worker.reference_period||'기준 별도 확인'})`,hint:'주민의 생활 장면·직장인의 업무 장면을 각각 입구로 둔 두 가지 체험 동선 후보. 두 모집단의 합산·중복·상품 선호를 뜻하지 않음.'});
    return {title:'흥부장 기획 단서',store:request.store?.name||'조사 매장',fields,opportunities};
  }
  function fieldText(f){return [`${f.number}. ${f.label}`, ...f.basis.map(t=>`조사에서 발견한 내용: ${t}`),...f.hints.map(t=>`데이터에서 연결한 아이디어: ${t}`),...(f.note?[f.note]:[]),...f.sources.map(s=>`근거: ${s.title} — ${s.url}`)].join('\n');}
  function text(model){return [model.title,model.store,'조사에서 발견한 사실과 그 사실에서 연결한 아이디어. 연결 아이디어는 고객 호응·행사 효과의 증거가 아닙니다.',...model.fields.map(fieldText),...model.opportunities.map(o=>`숨은 기회 후보\n관측: ${o.basis}\n기획 힌트: ${o.hint}`)].join('\n\n')+'\n';}
  function render(doc,target,model){
    target.replaceChildren();target.hidden=false;
    const el=(tag,text,parent,cls)=>{const n=doc.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;parent.append(n);return n;};
    el('p','PLANNING NOTES',target,'eyebrow');el('h2',model.title,target);
    el('p','조사 데이터가 기획에 주는 단서를 여섯 항목으로 모았습니다. 각 아이디어 옆의 근거를 통해 연결 이유를 볼 수 있습니다.',target,'planning-intro');
    const status=el('p','',target,'planning-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const grid=el('div','',target,'planning-grid');
    for(const f of model.fields){const card=el('article','',grid,'planning-card');el('span',String(f.number).padStart(2,'0'),card,'planning-number');el('h3',f.label,card);
      if(f.basis.length){el('h4','발견한 내용',card);const list=el('ul','',card);for(const line of f.basis)el('li',line,list);}else el('p','이 항목으로 연결할 조사 데이터가 없습니다.',card,'muted');
      if(f.hints.length){el('h4','데이터에서 연결한 아이디어',card);for(const line of f.hints)el('p',line,card);}
      if(f.note)el('p',f.note,card,'muted');
      if(f.sources.length){const detail=el('details','',card);el('summary',`근거 ${f.sources.length}개 보기`,detail);for(const s of f.sources){const a=el('a',s.title,detail);a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';}}
      const copy=el('button','이 항목 힌트 복사',card,'text-button');copy.type='button';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(fieldText(f));status.textContent=`${f.label} 힌트를 복사했어요.`;}catch{status.textContent='자동 복사를 사용할 수 없어요. 아래 텍스트를 선택해 복사해주세요.';const area=el('textarea',fieldText(f),card);area.setAttribute('aria-label',`${f.label} 복사용 힌트`);area.readOnly=true;area.focus();area.select();}});
    }
    for(const o of model.opportunities){const box=el('aside','',target,'planning-opportunity');el('h3','숨은 기회 후보',box);el('p',o.basis,box,'muted');el('p',o.hint,box);}
    el('p','판촉물·체험 아이디어는 기획 제안입니다. 타깃 상품, 행사 일정, 인력과 예산은 사용자가 결정합니다.',target,'planning-footnote');
  }
  return {build,text,render,safeUrl};
})();
if(typeof module!=='undefined')module.exports=SPOTPlanningHints;
