'use strict';
// Embeds are reader references. User-added media never enter research evidence.
const SPOTTrendBoard = (() => {
  const make=(tag,text,cls,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;if(parent)parent.append(e);return e;};
  function instagramURL(value){try{const u=new URL(value);if(u.protocol!=='https:'||!['instagram.com','www.instagram.com'].includes(u.hostname)||u.username||u.password)return null;const m=u.pathname.match(/^\/(p|reel)\/([A-Za-z0-9_-]{5,64})\/?$/);return m?`https://www.instagram.com/${m[1]}/${m[2]}/`:null;}catch{return null;}}
  function youtubeID(value){try{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password)return null;let id;if(['www.youtube.com','youtube.com','m.youtube.com'].includes(u.hostname))id=u.pathname==='/watch'?u.searchParams.get('v'):u.pathname.match(/^\/(?:shorts|embed)\/([\w-]+)$/)?.[1];else if(u.hostname==='youtu.be')id=u.pathname.slice(1);return /^[A-Za-z0-9_-]{11}$/.test(id||'')?id:null;}catch{return null;}}
  const link=(url,label,parent)=>{try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)return;const a=make('a',label,'text-button',parent);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{}};
  const short=(value,max=150)=>{const text=String(value||'').replace(/\s+/g,' ').trim();return text.length>max?text.slice(0,max)+'…':text;};
  function connectedQuestions(card,brief){
    const review=brief.research_review?.case_reviews?.find(r=>r.case_id===card.case_id);
    if(review&&(!['useful','generic'].includes(review.verdict)||review.dimensions?.transfer_logic!=='clear'||review.dimensions?.overclaim!=='clear'))return [];
    const observations=[...(brief.unique_local_signals||[]),...(brief.local_changes||[])];
    return (card.adaptation_hypotheses||[]).filter(h=>typeof h==='object'&&h.statement?.startsWith('지역 관측:')&&
      h.context_source_refs?.some(r=>observations.some(c=>c.module===r.module&&c.sources?.some(s=>s.source_id===r.source_id)&&
        (c.module==='local'||(h.kind==='research_question'&&['coherent','scope_checked'].includes(h.synthesis_review))||
          (c.population_kind==='sales'&&['day','time'].includes(c.distribution_kind))))));
  }
  function orderCases(brief){
    const score=c=>connectedQuestions(c,brief).length*100;
    return (brief.trend_patterns||[]).filter(c=>c.type==='reference_case').slice().sort((a,b)=>score(b)-score(a));
  }
  function collectVideos(brief,discovery={}){
    const seen=new Set(),videos=[];
    for(const s of [...(discovery.video_sources||[]),...(brief.trend_patterns||[]).flatMap(c=>c.sources||[])]){
      const id=youtubeID(s.source_url);if(id&&!seen.has(id)){seen.add(id);videos.push({id,source:s});}
    }
    return videos;
  }
  function videoMessage(discovery){
    if(discovery.video_status==='rate_limited')return 'YouTube 검색 요청이 잠시 제한되어 있습니다. 아래 기사로 체험 방식을 살펴보세요.';
    if(discovery.video_status==='provider_error')return 'YouTube 영상 검색을 잠시 이용할 수 없습니다. 아래 기사로 체험 방식을 살펴보세요.';
    return '수집한 영상이 있는 조사에서는 이곳에서 재생할 수 있습니다. 이번 결과의 행사 기사와 참여 방식은 체험 트렌드에서 살펴보세요.';
  }
  function player(parent,v,label){
    const screen=make('div',undefined,'trend-screen',parent),cover=make('button',undefined,'trend-video-cover',screen);cover.type='button';cover.setAttribute('aria-label',`${v.source.title||'참고 영상'} 재생`);
    const image=make('img',undefined,'',cover);image.src=`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`;image.alt=v.source.title||'YouTube 영상 썸네일';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>{image.hidden=true;cover.className+=' thumbnail-unavailable';});
    make('span','▶ 영상 재생','trend-play',cover);
    cover.addEventListener('click',()=>{
      // Configure the detached frame before its first navigation. The page's
      // no-referrer policy stays in place for other external resources.
      const frame=make('iframe');
      frame.referrerPolicy='strict-origin-when-cross-origin';
      frame.title=v.source.title||'체험 참고 영상';
      frame.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';
      frame.setAttribute('allowfullscreen','');
      frame.src=`https://www.youtube-nocookie.com/embed/${v.id}?autoplay=1`;
      screen.replaceChildren();screen.append(frame);
    });
    const copy=make('div',undefined,'trend-video-copy',parent);make('p',label,'trend-media-label',copy);make('h3',v.source.title||'체험 참고 영상','',copy);make('p',[v.source.source_name||'YouTube',v.source.published_at?.slice(0,10)].filter(Boolean).join(' · '),'muted',copy);
    link(v.source.source_url,'YouTube 원본 보기 ↗',copy);make('p','현장의 공간·참여 동선을 살펴볼 영상 참고입니다. 재생이 제한되면 원본에서 확인하세요.','media-caption',copy);
  }
  function renderOverview(doc,host,brief,discovery={}){
    host.replaceChildren();const videos=collectVideos(brief,discovery);host.hidden=false;
    const head=make('div',undefined,'overview-panel-head',host);make('h3','VIDEO · 전국 체험 참고 영상','',head);const more=make('button','체험 트렌드 보기 →','text-button',head);more.type='button';more.addEventListener('click',()=>doc.querySelector('.sidebar [data-view="trend"]')?.click());
    const body=make('div',undefined,'overview-video-body',host);if(videos.length)player(body,videos[0],'전국 체험 영상 참고');else make('p',videoMessage(discovery),'muted',body);
  }
  function render(doc,host,brief,request,evidence,discovery={}){
    host.replaceChildren();const items=brief.trend_patterns||[],cases=orderCases(brief);
    const key=`spot-media:${request?.request_id||brief.request_id||'unsaved'}`;let attachments={};
    try{attachments=JSON.parse(sessionStorage.getItem(key)||'{}');}catch{}
    if(!attachments||typeof attachments!=='object'||Array.isArray(attachments))attachments={};
    const save=()=>{try{sessionStorage.setItem(key,JSON.stringify(attachments));}catch{}};
    const intro=make('div',undefined,'trend-intro',host);make('p','TREND / FIELD NOTES','eyebrow',intro);make('h2','사람들은 무엇을 경험하고 있나요?','',intro);make('p','전국 행사와 체험 사례를 보고, 우리 매장에 참고할 연결점을 찾습니다.','muted',intro);
    const regional=make('section',undefined,'trend-regional-insights',host);make('h3','이 지역의 기획 출발점','',regional);
    const lenses=(brief.research_implications||[]).filter(r=>r.observation&&r.interpretation);
    const regionalCopy=lenses.length?(brief.overview?.area_summary||lenses[0].interpretation):(brief.overview?.primary_customer_signal||brief.overview?.area_summary||'지역 보도와 상권 지표를 개요에서 함께 살펴보세요.');
    const paragraphs=String(regionalCopy).split(/\n+/).map(p=>p.trim()).filter(Boolean);
    if(paragraphs.length===1){const sentences=paragraphs[0].match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g)||paragraphs;if(sentences.length>1)paragraphs.splice(0,1,sentences[0].trim(),sentences.slice(1).join('').trim());}
    paragraphs.forEach((text,index)=>make('p',text,index===0?'trend-regional-lead':'trend-regional-context',regional));
    const videos=collectVideos(brief,discovery);
    if(!cases.length){make('p','지역 관측을 중심으로 기획 질문을 정리했습니다.','empty',host);}
    const nav=make('div',undefined,'trend-case-nav',host),area=make('div',undefined,'',host);let moreCases;
    function select(card,index){
      area.replaceChildren();for(const [i,b]of [...nav.children].entries())b.setAttribute('aria-pressed',String(i===index));
      const news=make('section',undefined,'trend-news trend-selected-case',area);
      const questions=connectedQuestions(card,brief);
      const review=brief.research_review?.case_reviews?.find(r=>r.case_id===card.case_id);
      const baseline=(review&&(review.dimensions?.differentiation==='generic'||review.dimensions?.local_customer_fit!=='clear'))||
        (questions.length>0&&questions.every(h=>h.contribution==='baseline'));
      make('p',questions.length?(baseline?'BASIC CONNECTION / 기본 기획 참고':'REGIONAL CONNECTION / 지역 관측에 연결한 사례'):'NATIONAL REFERENCE / 전국 체험 참고','eyebrow',news);make('h3',card.event_name||'행사 참고 사례','trend-case-title',news);make('p',short(card.observation||card.description||''),'trend-case-summary',news);
      const sourcesPanel=make('details',undefined,'trend-source-reading',news);make('summary','기사 원문과 보도 내용','',sourcesPanel);
      const articles=(card.sources||[]).filter(s=>!youtubeID(s.source_url));
      articles.forEach((s,n)=>{const row=make('article',undefined,'trend-news-row',sourcesPanel);make('span',String(n+1).padStart(2,'0'),'story-number',row);const body=make('div',undefined,'',row);link(s.source_url,s.title||card.event_name||s.source_name||'원본 자료',body);make('p',[s.source_name||'출처',s.published_at?.slice(0,10)].filter(Boolean).join(' · '),'muted',body);});
      for(const s of card.sources||[])if(youtubeID(s.source_url))link(s.source_url,`이 사례의 영상 출처: ${s.title||'YouTube 원본'} ↗`,news);
      make('p',card.observation||'','',sourcesPanel);
      if(!questions.length){make('p','이 자료는 전국 행사의 참여 방식을 살펴볼 참고 기사입니다. 지역 인사이트는 위의 상권·지역 관측을 중심으로 읽습니다.','trend-evidence-level',news);return;}
      const applied=make('section',undefined,'trend-application',area);make('h3','이 사례에서 가져갈 것','',applied);
      const reading=make('div',undefined,'trend-application-grid',applied);
      const question=questions[0],statement=question.statement;
      const linked=statement.startsWith('지역 관측:');
      const action=linked?statement.split('사례에서 참고할 행동: ')[1]?.split(' 연결 단서:')[0]:null;
      const insight=lenses.find(r=>r.synthesis_id&&r.synthesis_id===question.synthesis_id);
      const mechanism=make('article',undefined,'',reading);make('h4','01  무엇을 했나','',mechanism);make('p',short(action||card.observation,200),'',mechanism);
      const observation=make('article',undefined,'',reading);make('h4','02  우리 지역에서 참고할 점','',observation);make('p',short(insight?.interpretation||'이 행사의 참여 방식을 지역의 안내·체험 접점에 참고할 수 있습니다.',220),'',observation);
      const adaptation=make('article',undefined,'',reading);make('h4','03  검토할 아이디어','',adaptation);
      const transfer=linked?(statement.split('연결 단서: ')[1]||statement):statement;
      make('p',short(insight?.question||transfer,220),'',adaptation);
      const reasons=make('section',undefined,'trend-selection-reasons',applied);make('h4','선정 이유와 연결 근거','',reasons);
      make('p',short(transfer,200),'',reasons);
      const data=make('details',undefined,'trend-source-reading',reasons);make('summary','연결에 사용한 수치와 출처','',data);make('p',statement.slice('지역 관측: '.length).split(' 사례에서 참고할 행동:')[0],'',data);
      const refs=make('div',undefined,'trend-context-links',data),seen=new Set();
      for(const [module,sources] of Object.entries(card.context_sources||{}))for(const source of sources){if(seen.has(source.source_url))continue;seen.add(source.source_url);link(source.source_url,`${module==='quant'?'상권 데이터':'지역 자료'} · ${source.title||source.source_name||'원본'} ↗`,refs);}
      const why=make('button','선정 이유와 연결 근거 보기 ↗','text-button',reasons);why.type='button';why.addEventListener('click',()=>evidence(card,'trend'));
      if(questions.length>1){const details=make('details',undefined,'trend-application-detail',applied);make('summary','다른 연결 방향 읽기','',details);for(const q of questions.slice(1))make('p',q.statement,'',details);}

    }
    cases.forEach((c,i)=>{const b=make('button',undefined,'',nav);b.type='button';b.hidden=i>=3;b.setAttribute('aria-label',c.event_name||'행사 참고 사례');make('span',String(i+1).padStart(2,'0'),'trend-case-number',b);const thumbnail=(c.sources||[]).map(s=>s.verification?.thumbnail_url).find(u=>/^https:\/\//.test(u||''));if(thumbnail){const img=make('img',undefined,'trend-case-thumbnail',b);img.src=thumbnail;img.alt='';img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>{img.hidden=true;});}const title=make('span',undefined,'trend-nav-copy',b);make('strong',c.event_name||'행사 참고 사례','',title);make('small',short(c.observation||'원본에서 사례 확인',65),'',title);b.addEventListener('click',()=>select(c,i));});if(cases.length>3){const more=make('button',`다른 사례 ${cases.length-3}개 보기 ↓`,'text-button trend-more-cases',host);host.insertBefore(more,area);moreCases=more;more.type='button';let expanded=false;more.addEventListener('click',()=>{expanded=!expanded;[...nav.children].forEach((b,i)=>b.hidden=!expanded&&i>=3);more.textContent=expanded?'사례 목록 접기 ↑':`다른 사례 ${cases.length-3}개 보기 ↓`;});}if(cases.length)select(cases[0],0);
    if(videos.length){
      const section=make('section',undefined,'trend-video-reference',host);make('p','VIDEO LIBRARY / 독립 참고 자료','eyebrow',section);make('h3','영상으로 살펴보는 체험 현장','',section);make('p','전국에서 수집한 별도의 참고 영상입니다. 뉴스 사례와 별도로 살펴볼 자료입니다.','muted',section);
      const body=make('div',undefined,'trend-reference-body',section),main=make('article',undefined,'trend-media-main',body),list=make('div',undefined,'trend-reference-list',body);
      function chooseVideo(v){main.replaceChildren();player(main,v,'전국 체험 현장 참고');for(const [i,b] of [...list.children].entries())b.setAttribute('aria-pressed',String(videos[i].id===v.id));attachments.reference_video=v.id;save();}
      for(const v of videos){const b=make('button',undefined,'trend-video-option',list);b.type='button';b.setAttribute('data-video-id',v.id);const img=make('img',undefined,'',b);img.src=`https://i.ytimg.com/vi/${v.id}/default.jpg`;img.alt='';img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>{img.hidden=true;});make('span',v.source.title||v.id,'',b);b.addEventListener('click',()=>chooseVideo(v));}
      chooseVideo(videos.find(v=>v.id===attachments.reference_video)||videos[0]);
      host.insertBefore(section,nav);
    }else{
      const section=make('section',undefined,'trend-video-reference',host);make('p','VIDEO / 체험 현장 참고','eyebrow',section);make('h3','영상으로 살펴보는 체험 현장','',section);make('p',videoMessage(discovery),'muted',section);host.insertBefore(section,nav);
    }
    const plan=make('details',undefined,'trend-search-plan',host);make('summary','검색 과정 · 검색어와 이유','',plan);
    if(discovery?.search_plan?.length)for(const row of discovery.search_plan){make('strong',row.query,'',plan);make('p',row.reason,'muted',plan);}else make('p','저장된 결과에는 검색 계획 기록이 없습니다.','muted',plan);
    const patterns=items.filter(c=>c.type!=='reference_case');if(patterns.length){const details=make('details',undefined,'trend-taxonomy',host);make('summary','검색 자료의 참여 방식 분류·보조 맥락','',details);make('p','검색 표현을 묶은 분류입니다. 시장 추세나 고객 선호의 증거로 읽지 않습니다.','muted',details);for(const c of patterns){const b=make('button',c.name||c.event_name||'자료 분류','text-button',details);b.type='button';b.addEventListener('click',()=>evidence(c,'trend'));}}
  }
  return {render,renderOverview,collectVideos,orderCases,connectedQuestions,instagramURL,youtubeID};
})();
if(typeof module!=='undefined')module.exports=SPOTTrendBoard;
