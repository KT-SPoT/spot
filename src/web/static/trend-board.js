'use strict';
// Embeds are reader references. User-added media never enter research evidence.
const SPOTTrendBoard = (() => {
  const make=(tag,text,cls,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;if(parent)parent.append(e);return e;};
  function instagramURL(value){try{const u=new URL(value);if(u.protocol!=='https:'||!['instagram.com','www.instagram.com'].includes(u.hostname)||u.username||u.password)return null;const m=u.pathname.match(/^\/(p|reel)\/([A-Za-z0-9_-]{5,64})\/?$/);return m?`https://www.instagram.com/${m[1]}/${m[2]}/`:null;}catch{return null;}}
  function youtubeID(value){try{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password)return null;let id;if(['www.youtube.com','youtube.com','m.youtube.com'].includes(u.hostname))id=u.pathname==='/watch'?u.searchParams.get('v'):u.pathname.match(/^\/(?:shorts|embed)\/([\w-]+)$/)?.[1];else if(u.hostname==='youtu.be')id=u.pathname.slice(1);return /^[A-Za-z0-9_-]{11}$/.test(id||'')?id:null;}catch{return null;}}
  const link=(url,label,parent)=>{try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)return;const a=make('a',label,'text-button',parent);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{}};
  const short=(value,max=150)=>{const text=String(value||'').replace(/\s+/g,' ').trim();return text.length>max?text.slice(0,max)+'…':text;};
  function collectVideos(brief,discovery={}){
    const seen=new Set(),videos=[];
    for(const s of [...(discovery.video_sources||[]),...(brief.trend_patterns||[]).flatMap(c=>c.sources||[])]){
      const id=youtubeID(s.source_url);if(id&&!seen.has(id)){seen.add(id);videos.push({id,source:s});}
    }
    return videos;
  }
  function player(parent,v,label){
    const screen=make('div',undefined,'trend-screen',parent),cover=make('button',undefined,'trend-video-cover',screen);cover.type='button';cover.setAttribute('aria-label',`${v.source.title||'참고 영상'} 재생`);
    const image=make('img',undefined,'',cover);image.src=`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`;image.alt=v.source.title||'YouTube 영상 썸네일';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>{image.hidden=true;cover.className+=' thumbnail-unavailable';});
    make('span','▶ 영상 재생','trend-play',cover);
    cover.addEventListener('click',()=>{screen.replaceChildren();const frame=make('iframe',undefined,'',screen);frame.src=`https://www.youtube-nocookie.com/embed/${v.id}?autoplay=1`;frame.title=v.source.title||'체험 참고 영상';frame.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';frame.referrerPolicy='strict-origin-when-cross-origin';frame.setAttribute('allowfullscreen','');});
    const copy=make('div',undefined,'trend-video-copy',parent);make('p',label,'trend-media-label',copy);make('h3',v.source.title||'체험 참고 영상','',copy);make('p',`${v.source.source_name||'YouTube'} · ${(v.source.published_at||'게시일 미확인').slice(0,10)}`,'muted',copy);
    link(v.source.source_url,'YouTube 원본 보기 ↗',copy);make('p','재생이 제한되면 원본에서 확인하세요. 영상의 호응·효과는 별도 확인이 필요합니다.','media-caption',copy);
  }
  function renderOverview(doc,host,brief,discovery={}){
    host.replaceChildren();const videos=collectVideos(brief,discovery);host.hidden=!videos.length;if(!videos.length)return;
    const head=make('div',undefined,'overview-panel-head',host);make('h3','VIDEO · 전국 체험 참고 영상','',head);const more=make('button','체험 트렌드 보기 →','text-button',head);more.type='button';more.addEventListener('click',()=>doc.querySelector('.sidebar [data-view="trend"]')?.click());
    const body=make('div',undefined,'overview-video-body',host);player(body,videos[0],'수집한 참고 영상 · 특정 기사와 동일 행사인지 미확인');
  }
  function render(doc,host,brief,request,evidence,discovery={}){
    host.replaceChildren();const items=brief.trend_patterns||[],cases=items.filter(c=>c.type==='reference_case');
    const key=`spot-media:${request?.request_id||brief.request_id||'unsaved'}`;let attachments={};
    try{attachments=JSON.parse(sessionStorage.getItem(key)||'{}');}catch{}
    if(!attachments||typeof attachments!=='object'||Array.isArray(attachments))attachments={};
    const save=()=>{try{sessionStorage.setItem(key,JSON.stringify(attachments));}catch{}};
    const intro=make('div',undefined,'trend-intro',host);make('p','TREND / FIELD NOTES','eyebrow',intro);make('h2','사람들은 무엇을 경험하고 있나요?','',intro);make('p','전국 행사와 체험 사례를 보고, 우리 매장에 참고할 연결점을 찾습니다.','muted',intro);
    const videos=collectVideos(brief,discovery);
    if(!cases.length){make('p','연결된 출처가 있는 행사 참고 사례를 확보하지 못했습니다.','empty',host);}
    const nav=make('div',undefined,'trend-case-nav',host),area=make('div',undefined,'',host);
    function select(card,index){
      area.replaceChildren();for(const [i,b]of [...nav.children].entries())b.setAttribute('aria-pressed',String(i===index));
      const id=String(card.case_id||index);const owned=attachments[id]&&typeof attachments[id]==='object'?attachments[id]:{};
      attachments[id]=owned;
      const news=make('section',undefined,'trend-news trend-selected-case',area);
      make('p','SELECTED CASE / 선택한 사례','eyebrow',news);make('h3',card.event_name||'행사 참고 사례','trend-case-title',news);make('p',short(card.observation||card.description||'사례 설명을 확보하지 못했습니다.'),'trend-case-summary',news);
      const articles=(card.sources||[]).filter(s=>!youtubeID(s.source_url));if(!articles.length)make('p','이 사례에 연결된 기사는 없습니다. 아래 원본 출처를 확인하세요.','muted',news);
      articles.forEach((s,n)=>{const row=make('article',undefined,'trend-news-row',news);make('span',String(n+1).padStart(2,'0'),'story-number',row);const body=make('div',undefined,'',row);link(s.source_url,s.title||card.event_name||s.source_name||'원본 자료',body);make('p',`${s.source_name||'출처'} · ${(s.published_at||'날짜 미확인').slice(0,10)}`,'muted',body);if(s.verification?.thumbnail_url&&/^https:\/\//.test(s.verification.thumbnail_url)){const img=make('img',undefined,'',row);img.src=s.verification.thumbnail_url;img.alt='기사 대표 이미지';img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>img.remove());}});
      for(const s of card.sources||[])if(youtubeID(s.source_url))link(s.source_url,`이 사례의 영상 출처: ${s.title||'YouTube 원본'} ↗`,news);
      const notes=make('p',card.case_detail?.status==='text_corroborated'?'원문 표현을 대조한 자료 · 고객 호응·성과 미확인':'검색 제목·요약 기반 자료 · 고객 호응·성과 미확인','trend-evidence-level',news);
      const full=make('details',undefined,'trend-source-reading',news);make('summary','보도 내용 전체 읽기','',full);make('p',card.observation||'내용 미확보','',full);
      const applied=make('section',undefined,'trend-application',area);make('p','FROM CASE TO STORE','eyebrow',applied);make('h3','이 사례에서 무엇을 참고할까?','',applied);
      const reading=make('div',undefined,'trend-application-grid',applied);
      const mechanism=make('article',undefined,'',reading);make('p','01 / 체험 방식','trend-reading-label',mechanism);make('h4','자료에서 확인한 장면','',mechanism);make('p',short(card.observation||'체험 방식은 원문 확인이 필요합니다.',180),'',mechanism);
      const adaptation=make('article',undefined,'',reading);make('p','02 / 매장 연결점','trend-reading-label',adaptation);make('h4','매장 응용은 조사 가설','',adaptation);const question=card.adaptation_hypotheses?.[0];make('p',short(typeof question==='string'?question:question?.statement||'응용 질문을 만들 자료가 미확보됐습니다.',180),'',adaptation);
      const check=make('article',undefined,'',reading);make('p','03 / 확인할 점','trend-reading-label',check);make('h4','호응과 효과는 별도 확인','',check);make('p','지역 고객 구성만으로 취향을 단정하지 않습니다. 체험 이해도와 참여 의향은 추가 확인할 항목입니다.','',check);
      const details=make('details',undefined,'trend-application-detail',area);make('summary','응용 질문 전체 · 선정 이유 · 고객 맥락','',details);for(const q of card.adaptation_hypotheses||[])make('p',q.statement||q,'',details);const why=make('button','선정 이유와 연결 근거 보기 ↗','text-button',details);why.type='button';why.addEventListener('click',()=>evidence(card,'trend'));
      const social=make('details',undefined,'trend-social',area);social.open=Array.isArray(owned.instagram)&&owned.instagram.length>0;make('summary','Instagram · 시각 참고 추가','',social);make('p','행사 공식 게시물이나 릴스를 추가하세요. 이 탭에만 보관되며 브리프·GPT·근거 수에 포함되지 않습니다.','muted',social);
      const form=make('form',undefined,'social-link-form',social),label=make('label','인스타그램 게시물 주소','',form),input=make('input',undefined,'',label);input.type='url';input.required=true;input.placeholder='https://www.instagram.com/p/…/';input.maxLength=300;const add=make('button','링크 추가','button',form);add.type='submit';const status=make('p','','muted',social);status.setAttribute('role','status');
      const links=Array.isArray(owned.instagram)?owned.instagram.map(instagramURL).filter(Boolean).slice(0,6):[];owned.instagram=links;
      function socialCard(url){const box=make('article',undefined,'social-reference',social);link(url,'Instagram 원본 보기 ↗',box);const preview=make('button','게시물 미리보기','text-button',box);preview.type='button';preview.addEventListener('click',()=>{preview.disabled=true;const quote=make('blockquote',undefined,'instagram-media',box);quote.setAttribute('data-instgrm-permalink',url);quote.setAttribute('data-instgrm-version','14');link(url,'Instagram에서 보기',quote);if(window.instgrm){window.instgrm.Embeds.process();return;}let script=doc.getElementById('instagram-embed-script');if(!script){script=doc.createElement('script');script.id='instagram-embed-script';script.src='https://www.instagram.com/embed.js';script.async=true;script.addEventListener('load',()=>window.instgrm?.Embeds?.process());script.addEventListener('error',()=>{status.textContent='미리보기를 불러오지 못했습니다. 원본 링크에서 확인해주세요.';preview.disabled=false;script.remove();});doc.body.append(script);}else script.addEventListener('load',()=>window.instgrm?.Embeds?.process(),{once:true});});const remove=make('button','제거','text-button',box);remove.type='button';remove.addEventListener('click',()=>{owned.instagram=owned.instagram.filter(v=>v!==url);save();select(card,index);});}
      links.forEach(socialCard);form.addEventListener('submit',event=>{event.preventDefault();const url=instagramURL(input.value);if(!url){status.textContent='공개 게시물 또는 릴스의 https://www.instagram.com/p/… 또는 /reel/… 주소를 입력해주세요.';return;}if(owned.instagram.length>=6){status.textContent='사례당 최대 6개를 추가할 수 있습니다.';return;}if(!owned.instagram.includes(url)){owned.instagram.push(url);save();socialCard(url);}input.value='';status.textContent='시각 참고 링크를 추가했습니다. AI 조사 근거에는 포함되지 않습니다.';});
      make('h4','공식 API로 해시태그 찾기','',social);
      make('p','행사·캠페인 해시태그를 직접 지정하세요. 검색은 7일에 서로 다른 30개까지이며 별도 Meta 승인이 필요합니다. 결과는 참고용이고, 이 행사와의 관련성은 원본에서 확인해주세요.','muted',social);
      const searchForm=make('form',undefined,'social-link-form',social),searchLabel=make('label','해시태그','',searchForm),query=make('input',undefined,'',searchLabel);query.required=true;query.maxLength=60;query.placeholder='행사 또는 캠페인 해시태그';
      const searchButton=make('button','공개 게시물 조회','button',searchForm);searchButton.type='submit';
      const searchStatus=make('p','','muted',social);searchStatus.setAttribute('role','status');const searchResults=make('div',undefined,'instagram-search-results',social);
      const errors={INSTAGRAM_NOT_CONFIGURED:'서버에 Instagram 토큰과 전문 계정 ID를 설정해야 합니다.',INSTAGRAM_TOKEN_EXPIRED:'Instagram 토큰이 만료됐거나 유효하지 않습니다. 서버 토큰을 갱신해주세요.',INSTAGRAM_PERMISSION_REQUIRED:'공개 해시태그 검색 권한이 부족합니다. Instagram Public Content Access 승인과 토큰 권한을 확인해주세요.',INSTAGRAM_RATE_LIMIT:'호출 제한에 도달했습니다. 잠시 후 다시 조회해주세요.',INSTAGRAM_HASHTAG_LIMIT:'7일 해시태그 한도에 도달했거나 사용 목록을 전부 확인하지 못했습니다.',SESSION_EXPIRED:'접속이 만료됐습니다. 새로고침해주세요.',INVALID_INSTAGRAM_QUERY:'공백·기호 없이 해시태그 하나를 입력해주세요.'};
      errors.INSTAGRAM_REQUEST_REJECTED='Meta가 조회 요청을 거절했습니다. 서버의 Instagram 전문 계정 ID와 API 접근 설정을 확인해주세요.';
      searchForm.addEventListener('submit',async event=>{event.preventDefault();searchButton.disabled=true;searchResults.replaceChildren();searchStatus.textContent='공식 API에서 확인하고 있습니다…';try{const response=await fetch('/api/instagram/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hashtag:query.value})});const data=await response.json();if(!response.ok){searchStatus.textContent=errors[data.error?.code]||'Instagram 조회를 완료하지 못했습니다. 잠시 후 다시 시도해주세요.';return;}searchStatus.textContent=data.items?.length?`#${data.hashtag} · ${data.items.length}개 · 조회 시각 ${data.collected_at} · 조사 근거에는 포함되지 않습니다.`:'이 해시태그에서 표시할 공개 게시물을 찾지 못했습니다.';for(const item of data.items||[]){const url=instagramURL(item.url);if(!url)continue;const row=make('article',undefined,'social-reference',searchResults);make('p',item.caption||'본문 없음','',row);link(url,'Instagram 원본 보기 ↗',row);const attach=make('button','이 사례의 참고 링크로 추가','text-button',row);attach.type='button';attach.addEventListener('click',()=>{if(owned.instagram.length>=6){searchStatus.textContent='사례당 참고 링크는 최대 6개입니다.';return;}if(!owned.instagram.includes(url)){owned.instagram.push(url);save();socialCard(url);}attach.disabled=true;});}}catch{searchStatus.textContent='서버에 연결하지 못했습니다. 연결 상태를 확인해주세요.';}finally{searchButton.disabled=false;}});
    }
    cases.forEach((c,i)=>{const b=make('button',undefined,'',nav);b.type='button';b.hidden=i>=3;b.setAttribute('aria-label',c.event_name||'행사 참고 사례');make('span',String(i+1).padStart(2,'0'),'trend-case-number',b);const title=make('span',undefined,'trend-nav-copy',b);make('strong',c.event_name||'행사 참고 사례','',title);make('small',short(c.observation||'원본에서 사례 확인',65),'',title);b.addEventListener('click',()=>select(c,i));});if(cases.length>3){const more=make('button',`다른 사례 ${cases.length-3}개 보기 ↓`,'text-button trend-more-cases',host);host.insertBefore(more,area);more.type='button';let expanded=false;more.addEventListener('click',()=>{expanded=!expanded;[...nav.children].forEach((b,i)=>b.hidden=!expanded&&i>=3);more.textContent=expanded?'사례 목록 접기 ↑':`다른 사례 ${cases.length-3}개 보기 ↓`;});}if(cases.length)select(cases[0],0);
    if(videos.length){
      const section=make('section',undefined,'trend-video-reference',host);make('p','VIDEO LIBRARY / 독립 참고 자료','eyebrow',section);make('h3','영상으로 살펴보는 체험 현장','',section);make('p','전국에서 수집한 별도의 참고 영상입니다. 위에서 선택한 뉴스 사례의 관련 영상이라는 의미는 아닙니다.','muted',section);
      const body=make('div',undefined,'trend-reference-body',section),main=make('article',undefined,'trend-media-main',body),list=make('div',undefined,'trend-reference-list',body);
      function chooseVideo(v){main.replaceChildren();player(main,v,'독립 참고 영상 · 행사 동일성·호응 미확인');for(const [i,b] of [...list.children].entries())b.setAttribute('aria-pressed',String(videos[i].id===v.id));attachments.reference_video=v.id;save();}
      for(const v of videos){const b=make('button',undefined,'trend-video-option',list);b.type='button';b.setAttribute('data-video-id',v.id);const img=make('img',undefined,'',b);img.src=`https://i.ytimg.com/vi/${v.id}/default.jpg`;img.alt='';img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>{img.hidden=true;});make('span',v.source.title||v.id,'',b);b.addEventListener('click',()=>chooseVideo(v));}
      chooseVideo(videos.find(v=>v.id===attachments.reference_video)||videos[0]);
    }
    const plan=make('details',undefined,'trend-search-plan',host);make('summary','검색 과정 · 검색어와 이유','',plan);
    if(discovery?.search_plan?.length)for(const row of discovery.search_plan){make('strong',row.query,'',plan);make('p',row.reason,'muted',plan);}else make('p','저장된 결과에는 검색 계획 기록이 없습니다.','muted',plan);
    const patterns=items.filter(c=>c.type!=='reference_case');if(patterns.length){const details=make('details',undefined,'trend-taxonomy',host);make('summary','검색 자료의 참여 방식 분류·보조 맥락','',details);make('p','검색 표현을 묶은 분류입니다. 시장 추세나 고객 선호의 증거로 읽지 않습니다.','muted',details);for(const c of patterns){const b=make('button',c.name||c.event_name||'자료 분류','text-button',details);b.type='button';b.addEventListener('click',()=>evidence(c,'trend'));}}
  }
  return {render,renderOverview,collectVideos,instagramURL,youtubeID};
})();
if(typeof module!=='undefined')module.exports=SPOTTrendBoard;
