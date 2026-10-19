/* Short observations from the completed brief; no provider calls. */
const SPOTPlanningHints = (() => {
  const labels={male:'남성',female:'여성',under_10:'10세 미만',teens:'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대','60_plus':'60대 이상',mon:'월',tue:'화',wed:'수',thu:'목',fri:'금',sat:'토',sun:'일','05_09':'05~09시','09_12':'09~12시','12_14':'12~14시','14_18':'14~18시','18_23':'18~23시','23_05':'23~05시'};
  const ages=['under_10','teens','20s','30s','40s','50s','60_plus'],days=['mon','tue','wed','thu','fri','sat','sun'],times=['05_09','09_12','12_14','14_18','18_23','23_05'];
  const valid=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=100;
  function peaks(c,keys){const rows=Object.entries(c.shares||{}).filter(([k,v])=>keys.includes(k)&&valid(v?.share_pct)).map(([k,v])=>[k,v.share_pct]);const max=Math.max(0,...rows.map(([,v])=>v));return max>0?rows.filter(([,v])=>v===max):[];}
  const values=(rows,day=false)=>rows.map(([k,v])=>`${labels[k]}${day?'요일':''} ${v}%`).join(' / ');
  function action(c){
    const t=String(c.observation||''),name=String(c.event_name||'');
    if(!c.sources?.length||!t||(t.includes('...')&&(t.includes('□')||name.includes('브리핑'))))return null;
    const tags=new Set([...(c.adaptation_hypotheses||[]).map(h=>h.mechanism),...(c.taxonomy_tags||[])]);
    if(tags.has('photo_sharing')&&/촬영|사진|영상/.test(t)&&/공유|SNS|소개|게시/.test(t))return '촬영·결과물 공유';
    if(tags.has('collectible_reward')&&/굿즈|소장|기념품|수집/.test(t)&&/구매|판매|증정|제공|소장|수집/.test(t))return '굿즈·기념품 제공 또는 판매';
    if(tags.has('direct_product_trial')&&/직접 (?:사용|체험)|게임을 체험|시연|써보|비교/.test(t))return '직접 사용·비교 체험';
    if(tags.has('mission_journey')&&/미션|스탬프/.test(t)&&/수행|완료|모으|달성/.test(t))return '미션·스탬프 참여';
    return null;
  }
  function build(brief={},request={}){
    const quant=(brief.unique_local_signals||[]).filter(c=>c.module==='quant');
    const pick=keys=>{for(const population of ['매출','유동인구','주거인구','직장인구']){const card=quant.find(c=>String(c.title||'').includes(population)&&peaks(c,keys).length);if(card)return [population==='매출'?'매출액':population,peaks(card,keys)];}return ['',[]];};
    const summary=['','','','','',''];
    const facility=quant.find(c=>c.title==='최다 주요시설 유형'&&c.value);
    if(facility)summary[0]=`${facility.value}가 주요 시설 유형인 상권.`;
    else {const present=quant.filter(c=>['주거인구','직장인구'].includes(c.title)&&typeof c.value==='number'&&Number.isFinite(c.value)&&c.value>0).map(c=>c.title);if(present.length)summary[0]=present.join('·')+'가 분포하는 상권.';}
    const [population,age]=pick(ages),[genderPopulation,gender]=pick(['male','female']);
    if(age.length)summary[1]=`${population}${population==='매출액'?'은':'는'} ${values(age)}가 가장 높음.`;
    if(gender.length)summary[1]+=(summary[1]?' ':'')+`${genderPopulation} 성별 비중은 ${values(gender)}가 가장 높음.`;
    const [dayPopulation,day]=pick(days),[timePopulation,time]=pick(times),parts=[];
    if(day.length)parts.push(`${dayPopulation} 요일 비중은 ${values(day,true)}가 가장 높음`);
    if(time.length)parts.push(`${timePopulation} 시간대 비중은 ${values(time)}가 가장 높음`);
    summary[3]=parts.join('. ')+(parts.length?'.':'');
    for(const c of brief.trend_patterns||[]){if(c.type!=='reference_case')continue;const review=brief.research_review?.case_reviews?.find(r=>r.case_id===c.case_id);if(review&&review.verdict!=='useful')continue;const idea=action(c);if(!idea)continue;const matched=age.map(([k])=>labels[k]).filter(label=>new RegExp('(?<!\\d)'+label).test(String(c.observation||'')));if(!matched.length)continue;summary[5]=`${matched.join('·')} 언급 행사: ‘${c.event_name||'전국 행사'}’ — ${idea}.`;break;}
    return {title:'흥부장 기획 단서',store:request.store?.name||'조사 매장',fields:['상권','타깃 고객','타깃 상품','행사 기간','직원 수','판촉물 예산'].map((label,i)=>({number:i+1,label,summary:summary[i]}))};
  }
  const fieldText=f=>`${f.number}. ${f.label}\n${f.summary}`;
  const text=model=>[model.title,model.store,...model.fields.map(fieldText)].join('\n\n')+'\n';
  function render(doc,target,model){
    target.replaceChildren();target.hidden=false;
    const el=(tag,text,parent,cls)=>{const n=doc.createElement(tag);n.textContent=text||'';if(cls)n.className=cls;parent.append(n);return n;};
    el('h2',model.title,target);const status=el('p','',target,'planning-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const grid=el('div','',target,'planning-grid');
    for(const f of model.fields){const card=el('article','',grid,'planning-card');el('span',String(f.number).padStart(2,'0'),card,'planning-number');el('h3',f.label,card);el('p',f.summary,card,'planning-summary');
      if(!f.summary)continue;
      const copy=el('button','복사',card,'text-button');copy.type='button';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(fieldText(f));status.textContent=`${f.label}을 복사했어요.`;}catch{status.textContent='텍스트를 선택해 복사해주세요.';const area=el('textarea',fieldText(f),card);area.readOnly=true;area.focus();area.select();}});
    }
    el('p','인구·매출, 성별·연령, 요일·시간대는 별도 집계입니다. 행사 아이디어는 참고안이며 연령대별 선호·효과나 예산을 확인한 결과가 아닙니다.',target,'planning-footnote');
  }
  return {build,text,render};
})();
if(typeof module!=='undefined')module.exports=SPOTPlanningHints;
