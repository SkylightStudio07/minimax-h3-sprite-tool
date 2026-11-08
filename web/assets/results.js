/* Sprite Lab results: result cards, list views (팀 갤러리, 내 작업, public showcase) and the result
 * detail page (#/jobs/<id>). Loaded before team.html's inline script; nothing here runs until the shell
 * calls in, so it may use the shell helpers ($, node, icon, url, api, toast, fmtDate, typeOf, me, ...).
 * Every action from the former gallery cards lives in `ResultActions`. */

const ANIMATION_LABELS={idle:'Idle · 대기',walk:'Walk · 걷기',run:'Run · 달리기',attack:'Attack · 공격',cast:'Cast · 스킬',hit:'Hit · 피격',death:'Death · 사망',jump:'Jump · 점프',custom:'Custom · 직접 설명'};
const CREATE_ROUTE={image:'create/image',video:'create/sprite',rigging:'create/rig',music:'create/music'};
const LIST_SIZE=24;
const jobKind=j=>['rigging','music','image'].includes(j.jobType)?j.jobType:'video';
const canEdit=j=>!!me&&(me.role==='admin'||j.userId===me.id);
const versioned=(path,revision)=>path?path+(path.includes('?')?'&':'?')+'workVersion='+(revision||0):'';
const hrefOf=path=>path.startsWith('#')?path:url(path);

function displayTitle(j){
  if(j.title)return j.title;
  const kind=jobKind(j);
  if(kind==='rigging')return j.publicLive2d?.title||(j.animationType&&!['idle','2D 리깅'].includes(j.animationType)?j.animationType:'2D 리깅 캐릭터');
  if(kind==='music')return j.animationType||'게임 BGM';
  return ANIMATION_LABELS[j.animationType]||j.animationType||'스프라이트';
}

function visibilityBadge(j){
  const kind=jobKind(j),badge=node('span',undefined,'ui-badge ui-badge--solid');
  if(kind==='video'||(kind==='rigging'&&j.publicLive2d)){
    badge.title=kind==='video'?'완료된 스프라이트는 로그인 없이 볼 수 있는 공개 갤러리에 표시됩니다.':'관리자가 공개 Live2D로 게시했습니다.';
    badge.append(icon('globe','ui-icon badge-icon'),document.createTextNode(kind==='video'?'공개':'공개 Live2D'));
  }else{badge.title='승인된 팀원만 볼 수 있습니다.';badge.textContent='팀 전용'}
  return badge;
}

function linkButton(label,path,{download=false,newTab=false,cls='ui-btn ui-btn--sm',iconName}={}){
  const a=node('a',undefined,cls);
  if(iconName)a.append(icon(iconName,'ui-icon ui-icon--sm'));
  a.append(node('span',label));a.href=hrefOf(path);
  if(download)a.download='';
  if(newTab){a.target='_blank';a.rel='noopener'}
  return a;
}
function actionButton(label,cls='ui-btn ui-btn--sm',iconName){
  const b=node('button',undefined,cls);b.type='button';
  if(iconName)b.append(icon(iconName,'ui-icon ui-icon--sm'));
  b.append(node('span',label));return b;
}
/* Runs an async action with the button disabled; errors become toasts. */
async function withBusy(button,work){
  button.disabled=true;button.setAttribute('aria-busy','true');
  try{return await work()}catch(error){toast(error.message,{tone:'danger'})}
  finally{button.disabled=false;button.removeAttribute('aria-busy')}
}

/* ------------------------------------------------------------- dialogs */
/* Resolves true/false, or the trimmed input text (null when cancelled) if `input` is given. */
function uiDialog({title,body,confirmLabel='확인',danger=false,input=null}){
  return new Promise(resolve=>{
    const dialog=node('dialog',undefined,'ui-modal'),head=node('div',undefined,'ui-modal__head'),content=node('div',undefined,'ui-modal__body'),foot=node('form',undefined,'ui-modal__foot');
    head.append(node('h2',title,'ui-h3'));
    if(body)content.append(node('p',body));
    let field=null;
    if(input){
      field=node('input',undefined,'ui-input');field.value=input.value||'';field.maxLength=input.maxLength||80;field.setAttribute('aria-label',input.label||title);
      field.style.marginTop='var(--sp-3)';
      field.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();dialog.close('ok')}});
      content.append(field);
    }
    foot.method='dialog';
    const cancel=node('button','취소','ui-btn ui-btn--ghost'),ok=node('button',confirmLabel,'ui-btn '+(danger?'ui-btn--danger-solid':'ui-btn--primary'));
    cancel.value='cancel';ok.value='ok';foot.append(cancel,ok);
    dialog.append(head,content,foot);document.body.append(dialog);
    dialog.addEventListener('close',()=>{const accepted=dialog.returnValue==='ok';resolve(field?(accepted?field.value.trim():null):accepted);dialog.remove()});
    dialog.showModal();(field||ok).focus();
  });
}

/* ---------------------------------------------------------------- menus */
let openMenu=null;
function closeMenus(){if(!openMenu)return;openMenu.hidden=true;openMenu.previousElementSibling?.setAttribute('aria-expanded','false');openMenu=null}
document.addEventListener('click',event=>{if(openMenu&&!event.target.closest('.menu-wrap'))closeMenus()});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenus()});
/* Keep the menu between the sticky top bar and the mobile tab bar: open downward, else upward,
 * else scroll it into the free area (CSS scroll-margin reserves the bars). */
function placeMenu(menu){
  const tabbar=document.querySelector('.tabbar'),header=document.querySelector('.shell-bar');
  const floor=(tabbar&&getComputedStyle(tabbar).display!=='none'?tabbar.getBoundingClientRect().top:innerHeight)-8;
  const ceiling=(header?header.getBoundingClientRect().bottom:0)+8;
  if(menu.getBoundingClientRect().bottom<=floor)return;
  menu.classList.add('menu--up');
  if(menu.getBoundingClientRect().top>=ceiling)return;
  menu.classList.remove('menu--up');
  menu.scrollIntoView({block:'nearest'});
}
/* items: {label, icon, href, download, newTab, onClick, danger}; falsy items are skipped. */
function moreMenu(items,label='더 보기'){
  const wrap=node('div',undefined,'menu-wrap'),toggle=node('button',undefined,'ui-btn ui-btn--ghost ui-btn--icon ui-btn--sm'),menu=node('div',undefined,'menu');
  toggle.type='button';toggle.setAttribute('aria-label',label);toggle.setAttribute('aria-haspopup','menu');toggle.setAttribute('aria-expanded','false');
  toggle.append(icon('more','ui-icon ui-icon--sm'));
  menu.setAttribute('role','menu');menu.hidden=true;
  for(const item of items.filter(Boolean)){
    let entry;
    if(item.href){
      entry=node('a',undefined,'menu-item');entry.href=hrefOf(item.href);
      if(item.download)entry.download='';
      if(item.newTab){entry.target='_blank';entry.rel='noopener'}
      entry.addEventListener('click',closeMenus);
    }else{
      entry=node('button',undefined,'menu-item');entry.type='button';
      // window.open inside onClick must stay synchronous with the click, so call before any await.
      entry.onclick=async()=>{closeMenus();try{await item.onClick()}catch(error){toast(error.message,{tone:'danger'})}};
    }
    entry.setAttribute('role','menuitem');
    if(item.danger)entry.classList.add('is-danger');
    if(item.icon)entry.append(icon(item.icon,'ui-icon ui-icon--sm'));
    entry.append(node('span',item.label));
    menu.append(entry);
  }
  toggle.onclick=event=>{
    event.stopPropagation();
    const show=menu.hidden;closeMenus();if(!show)return;
    menu.hidden=false;menu.classList.remove('menu--up');toggle.setAttribute('aria-expanded','true');openMenu=menu;
    placeMenu(menu);
    menu.querySelector('.menu-item')?.focus();
  };
  wrap.append(toggle,menu);return wrap;
}

/* ---------------------------------------------------------------- audio */
const sharedAudio=new Audio();let audioOwner=null;
function playButton(j,cls='ui-btn ui-btn--soft ui-btn--sm'){
  const b=actionButton('재생',cls,'play');b.dataset.audio=j.id;
  b.onclick=()=>{
    if(audioOwner===j.id&&!sharedAudio.paused){sharedAudio.pause();return}
    if(audioOwner!==j.id){sharedAudio.src=url(j.audio);audioOwner=j.id}
    sharedAudio.play().catch(error=>toast('재생할 수 없습니다. '+error.message,{tone:'danger'}));
  };
  syncAudioButton(b);return b;
}
function syncAudioButton(b){const playing=b.dataset.audio===audioOwner&&!sharedAudio.paused;b.querySelector('span').textContent=playing?'일시정지':'재생';b.querySelector('use').setAttribute('href',playing?'#i-pause':'#i-play')}
for(const type of ['play','pause','ended'])sharedAudio.addEventListener(type,()=>document.querySelectorAll('[data-audio]').forEach(syncAudioButton));
function stopAudio(){sharedAudio.pause();sharedAudio.removeAttribute('src');audioOwner=null}

/* -------------------------------------------------------------- actions */
const ResultActions={
  async remove(j){
    const body={video:'팀 갤러리와 공개 갤러리에서 사라지고 공유 링크도 비활성화됩니다. 파일은 서버에 보관됩니다.',rigging:'내부 공유 링크와 공개 Live2D도 비활성화됩니다. 파일은 서버에 보관됩니다.',image:'파일은 서버에 보관됩니다.',music:'파일은 서버에 보관됩니다.'}[jobKind(j)];
    if(!await uiDialog({title:'이 결과를 갤러리에서 내릴까요?',body,confirmLabel:'갤러리에서 내리기',danger:true}))return false;
    await api('api/jobs/'+j.id+'/delete',{});
    toast('결과를 갤러리에서 내렸습니다.',{tone:'success'});
    if(route.startsWith('jobs/'))location.hash='#/'+backRoute;else refreshResults();
    return true;
  },
  async internalUrl(j){return url((await api('api/jobs/'+j.id+'/shares',{kind:'internal'})).url)},
  async copyInternal(j){await navigator.clipboard.writeText(await ResultActions.internalUrl(j));toast('내부 공유 링크를 복사했습니다. 링크가 있는 팀원은 보고 편집할 수 있어요.',{tone:'success'})},
  async openInternal(j){
    // Open the tab inside the click so popup blockers allow it, then point it at the share URL.
    const tab=window.open('about:blank','_blank');
    try{const target=await ResultActions.internalUrl(j);if(tab){tab.opener=null;tab.location=target}else location.href=target}
    catch(error){if(tab)tab.close();throw error}
  },
  async openUnity(j){
    // Chrome may reject an external protocol navigation after the API await because the click activation
    // has expired. Reserve a small window synchronously, then navigate it once the signed link arrives.
    const launcher=window.open('about:blank','spritelab-unity-launcher','popup,width=420,height=220');
    if(launcher){launcher.document.title='Sprite Lab → Unity';launcher.document.body.textContent='Unity 연결을 준비하고 있습니다…'}
    try{
      const data=await api('api/jobs/'+j.id+'/unity-link',{});
      if(launcher){launcher.location.href=data.uri;setTimeout(()=>{try{launcher.close()}catch(_){}},2500)}else location.href=data.uri;
      toast('Unity 연결을 요청했습니다. 반응이 없으면 Unity 임포터를 설치하고 One-click Link를 활성화하세요.');
    }catch(error){if(launcher)launcher.close();throw error}
  },
  async buildV2(j){const d=await api('api/jobs/'+j.id+'/rig-v2',{revision:j.rigRevision||0});toast(`${d.boneCount}개 본의 V2 패키지를 만들었습니다.`,{tone:'success'});return d},
  async publish(j){
    const update=!!j.publicLive2d;
    const title=await uiDialog({title:update?'공개 Live2D를 현재 버전으로 갱신할까요?':'공개 Live2D로 게시할까요?',body:'로그인 없이 누구나 볼 수 있는 공개 Live2D 목록에 현재 PSD 복제본이 올라갑니다. 내부에서 다시 수정해도 공개본은 갱신하기 전까지 그대로입니다.',confirmLabel:update?'공개본 갱신':'게시',input:{value:j.publicLive2d?.title||displayTitle(j),label:'공개 이름'}});
    if(title===null)return false;
    if(!title){toast('공개 이름을 입력하세요.',{tone:'danger'});return false}
    const d=await api('api/jobs/'+j.id+'/public-live2d',{action:'publish',title});
    let copied=true;try{await navigator.clipboard.writeText(url(d.publicLive2d.url))}catch(_){copied=false}
    toast((update?'공개본을 현재 버전으로 갱신했습니다.':'공개 Live2D로 게시했습니다.')+(copied?' 링크를 복사했어요.':''),{tone:'success'});
    return true;
  },
  async unpublish(j){
    if(!await uiDialog({title:'공개 Live2D를 내릴까요?',body:'외부 접근이 바로 차단됩니다. 복제 파일은 서버에 보관됩니다.',confirmLabel:'공개 내리기',danger:true}))return false;
    await api('api/jobs/'+j.id+'/public-live2d',{action:'unpublish'});toast('공개 Live2D를 내렸습니다.',{tone:'success'});return true;
  },
  async restore(j,target){
    if(!await uiDialog({title:`작업 버전 v${target+1}을 새 버전으로 복원할까요?`,body:'현재 버전도 기록에 남습니다. V2 패키지와 공개본은 필요하면 다시 만들어야 합니다.',confirmLabel:'복원'}))return false;
    await api('api/jobs/'+j.id+'/rig-edit/restore',{revision:j.rigRevision||0,targetRevision:target});
    toast('이전 작업 버전을 새 버전으로 복원했습니다.',{tone:'success'});return true;
  },
  /* Resolves the new title (null when cancelled). An empty name falls back to the automatic one. */
  async rename(j){
    const title=await uiDialog({title:'결과 이름 바꾸기',body:'목록과 상세 화면에 보이는 이름입니다. 비워 두면 자동 이름으로 돌아갑니다.',confirmLabel:'저장',input:{value:j.title||'',label:'결과 이름',maxLength:60}});
    if(title===null)return null;
    const d=await api('api/jobs/'+j.id+'/title',{title});
    toast(d.title?`이름을 "${d.title}"(으)로 바꿨습니다.`:'자동 이름으로 되돌렸습니다.',{tone:'success'});
    return d.title||'';
  },
  async loopFix(j){await api('api/jobs/'+j.id+'/loop',{});toast('루프 검사를 마쳤습니다. 기존 영상과 시트도 그대로 보관됩니다.',{tone:'success'})},
  async extract(j,frameCount,backgroundRemoval='none'){await api('api/jobs/'+j.id+'/extract',{frameCount,removeBackground:backgroundRemoval!=='none',backgroundRemoval:backgroundRemoval==='none'?'flat':backgroundRemoval});toast(`${frameCount}프레임 시트를 추출했습니다.`,{tone:'success'})}
};

function refreshResults(){
  if(pane==='gallery')resultList('gallery').reload();
  else if(pane==='my')resultList('my').reload();
  else if(pane==='home')loadHome();
  else if(pane==='job'&&currentJob)openJob(currentJob.id);
}

/* ---------------------------------------------------------------- cards */
function resultArt(j){
  const kind=jobKind(j),[,tone]=typeOf(j),src=kind==='rigging'?versioned(j.composite,j.rigRevision):kind==='video'?j.poster:kind==='image'?j.image:null;
  const placeholder=()=>{const ph=node('div',undefined,'preview-ph preview-ph--'+tone);ph.append(icon(tone,'ui-icon ui-icon--lg'));return ph};
  if(!src)return placeholder();
  const img=node('img');img.src=url(src);img.alt='';img.loading='lazy';img.decoding='async';img.onerror=()=>img.replaceWith(placeholder());
  return img;
}
function attachHoverPreview(media,j){
  if(!matchMedia('(hover: hover)').matches)return;
  let video=null;
  media.addEventListener('pointerenter',()=>{video=node('video',undefined,'result-hover-video');video.muted=true;video.loop=true;video.playsInline=true;video.src=url(j.loopVideo||j.video);media.append(video);video.play().catch(()=>{})});
  media.addEventListener('pointerleave',()=>{video?.remove();video=null});
}
function recreateItem(j){return me?{label:'이 설정으로 다시 만들기',icon:'refresh',href:`#/${CREATE_ROUTE[jobKind(j)]}?from=${encodeURIComponent(j.id)}`}:null}
function renameItem(j){return canEdit(j)?{label:'이름 바꾸기',icon:'edit',onClick:async()=>{if(await ResultActions.rename(j)!==null)refreshResults()}}:null}
function removeItem(j){return canEdit(j)?{label:'갤러리에서 내리기',icon:'trash',danger:true,onClick:()=>ResultActions.remove(j)}:null}

function resultCard(j,{guest=false}={}){
  const kind=jobKind(j),[label,tone]=typeOf(j),detail='#/jobs/'+encodeURIComponent(j.id),sheet=j.loopSheet||j.spriteSheet;
  const card=node('article',undefined,'ui-card result-card'),media=node(guest?'div':'a',undefined,'ui-card__media result-media ui-checker'),badges=node('div',undefined,'result-badges'),type=node('span',undefined,'ui-badge ui-badge--'+tone);
  card.dataset.kind=kind;card.dataset.id=j.id;
  if(!guest){media.href=detail;media.setAttribute('aria-label',displayTitle(j)+' 자세히 보기')}
  type.append(icon(tone,'ui-icon badge-icon'),document.createTextNode(label));badges.append(type);
  if(!guest)badges.append(visibilityBadge(j));
  media.append(resultArt(j),badges);
  if(kind==='video'&&(j.loopVideo||j.video))attachHoverPreview(media,j);

  const body=node('div',undefined,'ui-card__body'),titleRow=node('div',undefined,'result-title-row'),title=node(guest?'span':'a',displayTitle(j),'ui-card__title result-title');
  if(!guest)title.href=detail;
  titleRow.append(title);
  if(kind==='rigging')titleRow.append(node('span','v'+((j.rigRevision||0)+1),'ui-badge'));
  const meta=[j.owner,fmtDate(j.created)];if(kind==='music'&&j.duration)meta.push(Math.round(j.duration)+'초');
  body.append(titleRow,node('span',meta.filter(Boolean).join(' · '),'ui-card__meta'));

  const actions=node('div',undefined,'ui-card__actions result-actions');
  if(guest){
    if(j.loopVideo||j.video)actions.append(linkButton('영상 보기',j.loopVideo||j.video,{newTab:true,iconName:'play'}));
    if(sheet)actions.append(linkButton('시트',sheet,{download:true,iconName:'download'}));
  }else if(kind==='image'){
    if(j.image)actions.append(linkButton('PNG 저장',j.image,{download:true,iconName:'download'}));
    actions.append(moreMenu([{label:'자세히 보기',icon:'eye',href:detail},renameItem(j),recreateItem(j),removeItem(j)]));
  }else if(kind==='video'){
    if(sheet){actions.append(linkButton('시트',sheet,{download:true,iconName:'download'}));actions.append(linkButton('GIF', 'api/jobs/'+encodeURIComponent(j.id)+'/sheet.gif'+(j.loopSheet?'?source=loopSheet':'?source=spriteSheet'),{download:true,iconName:'download'}))}
    actions.append(node('span',undefined,'ui-spacer'),moreMenu([
      {label:'자세히 보기',icon:'eye',href:detail},
      j.video&&{label:'영상 저장 (MP4)',icon:'download',href:j.video,download:true},
      j.transparentSheet&&{label:'투명 시트 저장',icon:'download',href:j.transparentSheet,download:true},
      renameItem(j),recreateItem(j),removeItem(j)]));
  }else if(kind==='rigging'){
    actions.append(canEdit(j)?linkButton('리깅 스튜디오','rigging-editor?job='+encodeURIComponent(j.id),{cls:'ui-btn ui-btn--soft ui-btn--sm',iconName:'edit'}):linkButton('자세히',detail,{iconName:'eye'}));
    actions.append(node('span',undefined,'ui-spacer'),moreMenu([
      {label:'자세히 보기',icon:'eye',href:detail},
      j.psd&&{label:'PSD 다운로드',icon:'download',href:j.psd,download:true},
      j.packageV2&&canEdit(j)&&{label:'Unity에서 열기',icon:'unity',onClick:()=>ResultActions.openUnity(j)},
      {label:'내부 공유 링크 복사',icon:'link',onClick:()=>ResultActions.copyInternal(j)},
      renameItem(j),recreateItem(j),removeItem(j)]));
  }else{
    if(j.audio)actions.append(playButton(j));
    actions.append(node('span',undefined,'ui-spacer'),moreMenu([
      {label:'자세히 보기',icon:'eye',href:detail},
      j.audio&&{label:'FLAC 저장',icon:'download',href:j.audio,download:true},
      j.score&&{label:'ABC 악보 저장',icon:'download',href:j.score,download:true},
      renameItem(j),recreateItem(j),removeItem(j)]));
  }
  card.append(media,body,actions);
  return card;
}

/* ---------------------------------------------------------------- lists */
const resultLists={};
const LIST_CONFIG={
  gallery:{pane:'galleryPane',grid:'galleryList',more:'galleryMore',count:'galleryCount',params:{}},
  my:{pane:'myDone',grid:'myList',more:'myMore',count:'myDoneCount',params:{owner:'me'}},
  public:{pane:'publicGallery',grid:'publicGalleryList',more:'publicMore',params:{size:12},guest:true}
};
function resultList(name){
  if(resultLists[name])return resultLists[name];
  const config=LIST_CONFIG[name],root=$(config.pane),state={type:'',owner:'',q:'',page:0,pages:1,total:0,ticket:0};
  const more=$(config.more),search=root.querySelector('[data-search]');
  function emptyState(){
    const filtered=state.type||state.owner||state.q,box=node('div',undefined,'empty');
    if(filtered){
      box.append(node('p','조건에 맞는 결과가 없어요.'));
      const reset=actionButton('필터 초기화','ui-btn ui-btn--sm');reset.style.marginTop='var(--sp-3)';
      reset.onclick=()=>{state.type=state.owner=state.q='';if(search)search.value='';root.querySelectorAll('[data-type]').forEach(b=>b.setAttribute('aria-pressed',String(!b.dataset.type)));const owner=root.querySelector('[data-owner]');if(owner)owner.value='';load(true)};
      box.append(reset);
    }else box.textContent=name==='my'?'아직 완료된 내 결과가 없어요. 홈에서 첫 작업을 만들어 보세요.':'아직 완료된 결과가 없습니다. 팀 서버에서 생성한 결과가 여기에 모입니다.';
    return box;
  }
  async function load(reset){
    const ticket=++state.ticket,page=reset?1:state.page+1,params=new URLSearchParams({page,size:LIST_SIZE,...config.params});
    for(const key of ['type','owner','q'])if(state[key])params.set(key,state[key]);
    if(more)more.setAttribute('aria-busy','true');
    try{
      const d=await api('api/gallery?'+params);
      if(ticket!==state.ticket)return;
      Object.assign(state,{page:d.page,pages:d.pages,total:d.total});
      const grid=$(config.grid);
      if(reset)grid.replaceChildren();
      grid.append(...d.jobs.map(j=>resultCard(j,{guest:!!config.guest})));
      if(!d.total)grid.replaceChildren(emptyState());
      if(config.count)$(config.count).textContent=d.total?String(d.total):'';
      if(more)more.hidden=d.page>=d.pages;
    }catch(error){if(ticket===state.ticket)toast(error.message,{tone:'danger'})}
    finally{if(ticket===state.ticket&&more)more.removeAttribute('aria-busy')}
  }
  root.querySelectorAll('[data-type]').forEach(button=>button.onclick=()=>{state.type=button.dataset.type;root.querySelectorAll('[data-type]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));load(true)});
  root.querySelector('[data-owner]')?.addEventListener('change',event=>{state.owner=event.target.value;load(true)});
  let timer;search?.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{state.q=search.value.trim();load(true)},300)});
  if(more)more.onclick=()=>load(false);
  return resultLists[name]={reload:()=>load(true),state};
}
function loadGallery(){resultList('gallery').reload()}
function refreshPublicGallery(){if(!me)resultList('public').reload()}

/* --------------------------------------------------------------- 내 작업 */
let myTab='done';
function setMyTab(tab){
  myTab=tab;
  document.querySelectorAll('#myTabs [data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===tab)));
  $('myDone').hidden=tab!=='done';$('myJobs').hidden=tab==='done';
  if(tab==='done')resultList('my').reload();else drawMyJobs();
}
function openMyWork(){setMyTab(myTab)}
/* Called by the shell after every /api/jobs poll. */
function drawMyJobs(){
  const ownJobs=jobsSnapshot.filter(mine),active=ownJobs.filter(j=>!terminal(j)),failed=ownJobs.filter(j=>['error','cancelled'].includes(j.state));
  const waiting=jobsSnapshot.filter(j=>j.state==='queued').sort((a,b)=>a.created-b.created);
  $('myActiveCount').textContent=active.length?String(active.length):'';
  $('myFailedCount').textContent=failed.length?String(failed.length):'';
  if(pane!=='my'||myTab==='done')return;
  const list=myTab==='active'?active:failed,target=$('myJobs');
  target.replaceChildren(...list.map(j=>jobCard(j,j.state==='queued'?waiting.indexOf(j)+1:0)));
  if(!list.length)empty(target,myTab==='active'?'진행 중인 내 작업이 없어요.':'최근 실패하거나 취소된 내 작업이 없어요.');
}

/* --------------------------------------------------------------- detail */
let detailTicket=0,currentJob=null;
const SETTING_LABELS={combatEffect:'공격 이펙트',effectStrength:'이펙트 강도',effectDescription:'이펙트 설명',pixelOutput:'도트 시트',pixelColorLock:'색 흔들림 줄이기',subjectType:'대상 유형',animationType:'애니메이션',samplingMode:'생성 모드',duration:'길이(초)',width:'너비',height:'높이',frameCount:'시트 프레임',motionPadding:'동작 여백(%)',motionSpeed:'동작 속도(배)',trimAction:'공격 앞뒤 멈춤 정리',motionStrength:'움직임 강도',facing:'방향',blinkMode:'눈 깜박임',loop:'루프',optimizeLoop:'루프 구간 자동 선택',stabilize:'크기 정규화',removeBackground:'단색 배경 누끼',backgroundTolerance:'누끼 강도',negativeEnabled:'CFG 네거티브',negativePrompt:'네거티브 프롬프트',cfgScale:'CFG 강도',seed:'Seed',prompt:'동작 설명·프롬프트',rigMode:'리깅 유형',separationBackend:'분리 엔진',resolution:'분리 해상도',steps:'품질 스텝',preserveOriginalEyes:'원본 눈 보존',preserveOriginalEyebrows:'원본 눈썹 보존',mouthState:'원본 입 상태',eyeInputMode:'눈 입력 방식',title:'제목',promptMode:'프롬프트 방식',preset:'프리셋',vocalMode:'보컬',cot:'CoT',notes:'메모'};

function detailSection(title,desc){
  const section=node('section',undefined,'detail-section'),head=node('div',undefined,'detail-section__head');
  head.append(node('h2',title));if(desc)head.append(node('p',desc));
  section.append(head);return section;
}
function detailRow(label,desc,...controls){
  const row=node('div',undefined,'detail-row'),text=node('div',undefined,'detail-row__text'),actions=node('div',undefined,'detail-row__actions');
  text.append(node('b',label));if(desc)text.append(node('span',desc));
  actions.append(...controls.filter(Boolean));row.append(text,actions);return row;
}
function settingsSection(j){
  const entries=Object.entries(j.settings||{}).filter(([key,value])=>SETTING_LABELS[key]&&value!==null&&value!==''&&typeof value!=='object');
  if(!entries.length)return null;
  const details=node('details',undefined,'detail-section detail-section--late detail-settings'),summary=node('summary','생성 설정'),list=node('dl');
  for(const [key,value] of entries){list.append(node('dt',SETTING_LABELS[key]),node('dd',key==='combatEffect'&&value==='subtle'?'작은 검기 · 짧고 옅은 칼 궤적':typeof value==='boolean'?(value?'켜짐':'꺼짐'):String(value)))}
  details.append(summary,list);return details;
}

async function openJob(id){
  const ticket=++detailTicket,root=$('jobDetail');
  stopAudio();
  root.replaceChildren(node('div',undefined,'ui-skeleton detail-skeleton'));
  try{
    const {job}=await api('api/gallery/'+encodeURIComponent(id));
    if(ticket!==detailTicket)return;
    currentJob=job;renderDetail(job);
  }catch(error){
    if(ticket!==detailTicket)return;
    currentJob=null;
    const box=node('div',undefined,'ui-empty'),glyph=node('span',undefined,'ui-empty__icon');glyph.append(icon('gallery','ui-icon ui-icon--lg'));
    box.append(glyph,node('b','결과를 찾을 수 없어요'),node('span',error.message,'ui-small'),linkButton('목록으로','#/'+backRoute,{cls:'ui-btn ui-btn--sm'}));
    root.replaceChildren(box);
  }
}

function renderDetail(j){
  const kind=jobKind(j),[label,tone]=typeOf(j),root=$('jobDetail');
  const backLabel={my:'내 작업',home:'홈'}[backRoute]||'팀 갤러리';
  baseTitle=displayTitle(j)+' · Sprite Lab';updateTitle();
  $('crumb').replaceChildren(document.createTextNode(backLabel+' / '),node('b',displayTitle(j)));

  const head=node('header',undefined,'detail-head'),back=linkButton(backLabel,'#/'+backRoute,{cls:'ui-btn ui-btn--ghost ui-btn--sm detail-back',iconName:'arrow-left'});
  const titleRow=node('div',undefined,'detail-title-row'),glyph=node('span',undefined,'feature-icon feature-icon--'+tone),text=node('div',undefined,'detail-title'),badges=node('div',undefined,'detail-badges'),actions=node('div',undefined,'detail-actions');
  glyph.append(icon(tone,'ui-icon ui-icon--lg'));
  const typeBadge=node('span',undefined,'ui-badge ui-badge--'+tone);typeBadge.append(icon(tone,'ui-icon badge-icon'),document.createTextNode(label));
  badges.append(typeBadge,visibilityBadge(j));
  if(kind==='rigging')badges.append(node('span','작업 버전 v'+((j.rigRevision||0)+1),'ui-badge'));
  badges.append(node('span',[j.owner,fmtDate(j.created)].filter(Boolean).join(' · '),'detail-meta'));
  const heading=node('div',undefined,'detail-heading');heading.append(node('h1',displayTitle(j)));
  if(canEdit(j)){const rename=node('button',undefined,'ui-btn ui-btn--ghost ui-btn--icon ui-btn--sm');rename.type='button';rename.setAttribute('aria-label','이름 바꾸기');rename.title='이름 바꾸기';rename.append(icon('edit','ui-icon ui-icon--sm'));rename.onclick=async()=>{try{if(await ResultActions.rename(j)!==null)openJob(j.id)}catch(error){toast(error.message,{tone:'danger'})}};heading.append(rename)}
  text.append(heading,badges);

  if(kind==='rigging'&&canEdit(j))actions.append(linkButton('리깅 스튜디오 열기','rigging-editor?job='+encodeURIComponent(j.id),{cls:'ui-btn ui-btn--primary',iconName:'edit'}));
  if(kind==='video'&&(j.loopSheet||j.spriteSheet))actions.append(linkButton('시트 다운로드',j.loopSheet||j.spriteSheet,{download:true,cls:'ui-btn ui-btn--primary',iconName:'download'}));
  if(canEdit(j)&&kind!=='music')actions.append((()=>{const b=actionButton('캐릭터에 연결','ui-btn','folder');b.onclick=()=>withBusy(b,()=>attachCharacterResult(j));return b})());
  if(canEdit(j)&&kind==='video'&&(j.video||j.loopVideo))actions.append(linkButton('반복 구간 고르기','loop-editor?job='+encodeURIComponent(j.id),{cls:'ui-btn ui-btn--primary',iconName:'edit'}));
  if(canEdit(j)&&(kind==='video'&&(j.spriteSheet||j.loopSheet)||kind==='image'&&j.settings?.sheetLayout))actions.append(linkButton('프레임 편집','frame-editor?job='+encodeURIComponent(j.id),{cls:'ui-btn',iconName:'edit'}));
  if(kind==='music'&&j.audio)actions.append(playButton(j,'ui-btn ui-btn--primary'));
  if(j.settings)actions.append(linkButton('이 설정으로 다시 만들기',`#/${CREATE_ROUTE[kind]}?from=${encodeURIComponent(j.id)}`,{cls:'ui-btn',iconName:'refresh'}));
  if(canEdit(j))actions.append(moreMenu([{...renameItem(j),onClick:async()=>{if(await ResultActions.rename(j)!==null)openJob(j.id)}},removeItem(j)],'결과 관리'));
  titleRow.append(glyph,text,actions);head.append(back,titleRow);

  const grid=node('div',undefined,'detail-grid'),main=node('div',undefined,'detail-main'),side=node('aside',undefined,'detail-side');
  if(kind==='image')renderImageDetail(j,main,side);
  else if(kind==='video')renderSpriteDetail(j,main,side);
  else if(kind==='rigging')renderRigDetail(j,main,side);
  else renderMusicDetail(j,main,side);
  const settings=settingsSection(j);if(settings)side.append(settings);
  grid.append(main,side);root.replaceChildren(head,grid);
}

function segmented(options,onSelect,label){
  const group=node('div',undefined,'ui-seg');group.setAttribute('role','group');group.setAttribute('aria-label',label);
  options.forEach(([text,value],index)=>{const b=node('button',text);b.type='button';b.setAttribute('aria-pressed',String(index===0));b.onclick=()=>{group.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));onSelect(value)};group.append(b)});
  return group;
}

function renderSpriteDetail(j,main,side){
  const stage=node('div',undefined,'detail-stage ui-checker'),video=node('video');
  video.controls=true;video.muted=true;video.loop=j.loop!==false;video.playsInline=true;video.preload='metadata';
  if(j.poster)video.poster=url(j.poster);
  if(j.loopVideo||j.video)video.src=url(j.loopVideo||j.video);
  stage.append(video);main.append(stage);
  if(j.loopVideo&&j.video)main.append(segmented([['루프 보정본',j.loopVideo],['원본 영상',j.video]],path=>{video.src=url(path);video.play().catch(()=>{})},'영상 선택'));

  const sheets=[['수정 시트 · v'+((j.frameWorkspace?.revision||0)+1),j.frameWorkspace?.sheet],['원본 시트',j.spriteSheet],['투명 시트',j.transparentSheet],['루프 보정 시트',j.loopSheet],['루프 보정 투명',j.loopTransparentSheet],...Object.entries(j.exportSheets||{}).map(([key,path])=>[key.split('_')[1]+'프레임'+(key.endsWith('_transparent')?' 투명':' 재추출'),path])].filter(([,path])=>path);
  if(sheets.length){
    const viewer=detailSection('스프라이트 시트','시트를 누르면 원본 크기로 새 탭에서 열립니다.'),box=node('a',undefined,'sheet-box ui-checker'),img=node('img');
    img.alt='스프라이트 시트';box.target='_blank';box.rel='noopener';box.append(img);
    const show=path=>{img.src=url(path);box.href=url(path)};show(sheets[0][1]);
    if(sheets.length>1)viewer.append(segmented(sheets,show,'시트 선택'));
    viewer.append(box);main.append(viewer);
  }

  const downloads=detailSection('다운로드');
  for(const [name,desc,path,key] of [['스프라이트 시트','생성 영상에서 고르게 뽑은 프레임',j.spriteSheet,'spriteSheet'],['투명 시트','배경을 제거한 PNG 시트',j.transparentSheet,'transparentSheet'],['루프 보정 시트','자연스럽게 이어지는 구간으로 자른 시트',j.loopSheet,'loopSheet'],['루프 보정 투명 시트','',j.loopTransparentSheet,'loopTransparentSheet'],['영상 (MP4)','정규화된 결과 영상',j.video],['루프 보정 영상 (MP4)','',j.loopVideo],['H3 원본 영상','정규화 전 모델 출력',j.rawVideo]])
    if(path)downloads.append(detailRow(name,desc,linkButton(key?'PNG 저장':'저장',path,{download:true,iconName:'download'}),key&&linkButton('GIF · 인계용','api/jobs/'+encodeURIComponent(j.id)+'/sheet.gif?source='+encodeURIComponent(key),{download:true,iconName:'download'})));
  for(const [key,path] of Object.entries(j.exportSheets||{}))downloads.append(detailRow(key.split('_')[1]+'프레임'+(key.endsWith('_transparent')?' 투명 시트':' 재추출 시트'),'',linkButton('PNG 저장',path,{download:true,iconName:'download'}),linkButton('GIF · 인계용','api/jobs/'+encodeURIComponent(j.id)+'/sheet.gif?source='+encodeURIComponent('export:'+key),{download:true,iconName:'download'})));
  if(j.frameWorkspace?.id)downloads.append(detailRow('수정 프레임 GIF','저장된 재생 속도로 내보냅니다.',linkButton('GIF 저장','api/frames/'+encodeURIComponent(j.frameWorkspace.id)+'/animation.gif',{download:true,iconName:'download'})));
  downloads.append(node('p','시트 GIF는 저장된 재생 속도를 사용하며, 속도 정보가 없으면 8FPS입니다. 프레임 편집에서 속도·재생 구간을 바꿔 저장할 수 있습니다.','detail-text'));
  side.append(downloads);

  if(canEdit(j)){
    const tools=detailSection('도구','영상을 새로 생성하지 않고 기존 결과를 다시 처리합니다.');
    if(j.loopReport){
      const quality={good:'좋음',fair:'보통',needs_review:'직접 확인 필요'}[j.loopReport.quality]||'직접 확인 필요';
      tools.append(detailRow('루프 연결 추정 · '+quality,j.loopReport.method==='trim'?`${j.loopReport.inputSeconds}초 → ${j.loopReport.outputSeconds}초로 잘랐습니다.`:'원래 길이를 유지했습니다.'));
    }
    if(j.loop!==false&&(!j.loopReport||j.loopReport.reason==='processing_failed')){
      const fix=actionButton('보정본 만들기','ui-btn ui-btn--sm','refresh');
      fix.onclick=()=>withBusy(fix,async()=>{await ResultActions.loopFix(j);openJob(j.id)});
      tools.append(detailRow('루프 보정본 만들기','시작과 끝이 매끄럽게 이어지는 구간을 찾아 별도 영상과 시트를 만듭니다.',fix));
    }
    const count=node('input',undefined,'ui-input extract-count');count.type='number';count.min='2';count.max='64';count.step='1';count.value='64';count.setAttribute('aria-label','재추출 프레임 수');
    const matte=node('select',undefined,'ui-input');matte.setAttribute('aria-label','재추출 배경 제거');for(const [value,label] of [['none','배경 유지'],['ai','AI 배경 제거'],['ai-smooth','AI · 윤곽 다듬기 (실험적)'],['flat','단색 배경 제거']])matte.add(new Option(label,value));
    const extract=actionButton('추출','ui-btn ui-btn--sm');
    extract.onclick=()=>{if(!count.reportValidity())return;withBusy(extract,async()=>{await ResultActions.extract(j,Number(count.value),matte.value);openJob(j.id)})};
    tools.append(detailRow('시트 다시 추출','2~64프레임 · 원본 보존 · AI 제거는 프레임 수에 따라 시간이 걸려요.',count,matte,extract));
    side.append(tools);
  }
  const note=node('div',undefined,'ui-alert ui-alert--neutral');note.append(icon('globe'),node('span','완료된 스프라이트 영상과 시트는 로그인 없이 볼 수 있는 공개 갤러리에도 표시됩니다. 원하지 않으면 갤러리에서 내리세요.'));
  side.append(note);
}

function renderRigDetail(j,main,side){
  const editable=canEdit(j),editor=mode=>'rigging-editor?job='+encodeURIComponent(j.id)+(mode?'&mode='+mode:'');
  const versions=j.rigVersions?.length?j.rigVersions:[{revision:j.rigRevision||0,label:`작업 버전 v${(j.rigRevision||0)+1}`,current:true,composite:j.composite,psd:j.psd,package:j.package}];
  const stage=node('div',undefined,'detail-stage ui-checker'),img=node('img'),missing=node('div',undefined,'preview-ph preview-ph--rig');img.alt='2D 리깅 합성 결과';
  missing.append(icon('rig','ui-icon ui-icon--lg'),node('span','합성 이미지를 불러오지 못했어요','ui-small'));missing.hidden=true;stage.append(missing);
  img.onerror=()=>{img.hidden=true;missing.hidden=false};img.onload=()=>{missing.hidden=true};
  let player=null;
  const showImage=path=>{player?.remove();player=null;missing.hidden=true;img.hidden=false;img.src=url(path)};
  showImage(versioned(j.composite,j.rigRevision));stage.append(img);
  const views=[['합성 이미지','image']];if(j.player)views.push(['움직임 미리보기','player']);
  const viewSwitch=segmented(views,value=>{if(value==='player'){img.hidden=true;missing.hidden=true;player=node('iframe',undefined,'detail-player');player.src=url(j.player);player.title='2D 리깅 움직임 미리보기';player.allow='fullscreen';stage.append(player)}else showImage(versioned(j.composite,j.rigRevision))},'미리보기 종류');
  main.append(stage);if(views.length>1)main.append(viewSwitch);

  const historySection=detailSection('작업 버전 기록','저장할 때마다 새 버전이 생깁니다. 이전 버전을 새 버전으로 복원할 수 있어요.'),timeline=node('ol',undefined,'version-list');
  for(const version of [...versions].sort((a,b)=>b.revision-a.revision)){
    const item=node('li',undefined,'version-item'+(version.current?' is-current':'')),info=node('div',undefined,'version-info'),buttons=node('div',undefined,'version-actions');
    info.append(node('b',version.label+(version.current?' · 현재':'')),node('span',version.created?fmtDate(version.created)+' 저장':'','version-date'));
    const view=actionButton('보기','ui-btn ui-btn--ghost ui-btn--sm','eye');
    view.onclick=()=>{viewSwitch.querySelector('button')?.click();showImage(versioned(version.composite,version.revision));stage.scrollIntoView({behavior:'smooth',block:'nearest'})};
    buttons.append(view);
    if(version.psd)buttons.append(linkButton('PSD',version.psd,{download:true,cls:'ui-btn ui-btn--ghost ui-btn--sm'}));
    if(version.package)buttons.append(linkButton('파츠 ZIP',version.package,{download:true,cls:'ui-btn ui-btn--ghost ui-btn--sm'}));
    if(editable&&!version.current){const restore=actionButton('복원','ui-btn ui-btn--sm');restore.onclick=()=>withBusy(restore,async()=>{if(await ResultActions.restore(j,version.revision))openJob(j.id)});buttons.append(restore)}
    item.append(info,buttons);timeline.append(item);
  }
  historySection.classList.add('detail-section--late');historySection.append(timeline);main.append(historySection);

  if(editable){
    const studio=detailSection('리깅 스튜디오에서 다듬기','잘못 분리된 파츠를 고치고, 표정·본·애니메이션까지 한 편집기에서 작업합니다.'),modes=node('div',undefined,'studio-modes');
    for(const [name,desc,iconName,mode] of [['레이어','지우기 · 원본 복원 · 병합 · 순서','rig',''],['표정 차분','눈·입·눈썹 직접 그리기','smile','expressions'],['본 · 포즈','관절 위치 · 파츠 연결 · IK','bone','bones'],['애니메이션','타임라인 · 키프레임 · 클립','clapper','animation'],['화질 개선','AI · 레이어 2배/4배 · 확대본 적용','image','quality']]){
      const card=node('a',undefined,'studio-mode');card.href=url(editor(mode));
      const glyph=node('span',undefined,'feature-icon feature-icon--sm feature-icon--rig');glyph.append(icon(iconName));
      card.append(glyph,node('b',name),node('span',desc));modes.append(card);
    }
    studio.append(modes,linkButton('편집 가이드 · 단축키','guide#rig-studio',{newTab:true,cls:'ui-btn ui-btn--ghost ui-btn--sm',iconName:'guide'}));
    side.append(studio);
  }else{
    const note=node('div',undefined,'ui-alert ui-alert--neutral');note.append(icon('info'),node('span','리깅 스튜디오 편집은 작성자와 관리자만 할 수 있어요. 내부 공유 링크로 열면 팀원도 함께 편집할 수 있습니다.'));side.append(note);
  }

  const exportsSection=detailSection('내보내기');
  if(j.psd)exportsSection.append(detailRow('PSD 레이어 원본','포토샵·클립 스튜디오에서 여는 레이어 파일',linkButton('저장',j.psd,{download:true,iconName:'download'})));
  if(j.package)exportsSection.append(detailRow('Unity V1 · 파츠','SpriteRenderer 프리팹 · 깜박임·입·머리카락 idle',linkButton('저장',j.package,{download:true,iconName:'download'})));
  const v2Desc=(j.rigV2BoneCount?j.rigV2BoneCount+'개 ':'')+'본·메시·자동 웨이트 초안. Unity에서 본 위치와 웨이트를 검수하세요.';
  if(j.packageV2){
    exportsSection.append(detailRow('Unity V2 · 본·메시',v2Desc,linkButton('저장',j.packageV2,{download:true,iconName:'download'}),editable&&(()=>{const b=actionButton('Unity에서 열기','ui-btn ui-btn--sm','unity');b.onclick=()=>{ResultActions.openUnity(j).catch(error=>toast(error.message,{tone:'danger'}))};return b})()));
  }else if(editable){
    const build=actionButton('생성','ui-btn ui-btn--sm');
    build.onclick=()=>withBusy(build,async()=>{await ResultActions.buildV2(j);openJob(j.id)});
    exportsSection.append(detailRow('Unity V2 · 본·메시',v2Desc+' 레이어를 다듬은 뒤 만드는 것을 권장합니다.',build));
  }
  if(editable)exportsSection.append(detailRow('레이어 화질 개선','AI · 2배/4배 · PSD·Unity V2·갤러리 적용',linkButton('열기',editor('quality'),{iconName:'edit'})));
  exportsSection.append(detailRow('Unity 임포터','V1·V2 패키지를 가져오는 Unity 패키지. 업데이트가 있으면 다시 받으세요.',linkButton('받기','unity-importer.zip',{download:true,iconName:'unity'})));
  side.append(exportsSection);

  const share=detailSection('공유');
  const open=actionButton('열기','ui-btn ui-btn--sm','external');open.onclick=()=>{ResultActions.openInternal(j).catch(error=>toast(error.message,{tone:'danger'}))};
  const copy=actionButton('복사','ui-btn ui-btn--sm','link');copy.onclick=()=>withBusy(copy,()=>ResultActions.copyInternal(j));
  share.append(detailRow('내부 공유 링크','링크가 있는 팀원은 로그인 없이 미리보기와 편집을 할 수 있어요.',open,copy));
  if(me?.role==='admin'){
    const publish=actionButton(j.publicLive2d?'공개본 갱신':'게시',j.publicLive2d?'ui-btn ui-btn--sm':'ui-btn ui-btn--soft ui-btn--sm','globe');
    publish.onclick=()=>withBusy(publish,async()=>{if(await ResultActions.publish(j))openJob(j.id)});
    const controls=[j.publicLive2d&&linkButton('열기',j.publicLive2d.url,{newTab:true,iconName:'external'}),publish];
    if(j.publicLive2d){const off=actionButton('내리기','ui-btn ui-btn--danger ui-btn--sm');off.onclick=()=>withBusy(off,async()=>{if(await ResultActions.unpublish(j))openJob(j.id)});controls.push(off)}
    share.append(detailRow('공개 Live2D',j.publicLive2d?`"${j.publicLive2d.title}"으로 공개 중 · 내부 수정은 갱신해야 반영됩니다.`:'로그인 없이 누구나 움직여 볼 수 있게 게시합니다.',...controls));
  }else if(j.publicLive2d){
    share.append(detailRow('공개 Live2D',`"${j.publicLive2d.title}"으로 공개 중`,linkButton('열기',j.publicLive2d.url,{newTab:true,iconName:'external'})));
  }
  side.append(share);
}

function renderMusicDetail(j,main,side){
  const stage=node('div',undefined,'detail-stage detail-stage--music'),glyph=node('span',undefined,'music-glyph');
  glyph.append(icon('music','ui-icon'));
  const audio=node('audio');audio.controls=true;audio.preload='metadata';if(j.audio)audio.src=url(j.audio);
  stage.append(glyph,audio);main.append(stage);
  if(j.promptReason){const reason=detailSection('프롬프트 결정');reason.append(node('p',j.promptReason,'detail-text'));main.append(reason)}
  if(j.resolvedPrompt){const prompt=detailSection('적용 프롬프트');prompt.append(node('pre',j.resolvedPrompt,'detail-pre'));main.append(prompt)}
  if(j.vocalMode==='lyrics'&&j.lyrics){const lyrics=detailSection('가사');lyrics.append(node('pre',j.lyrics,'detail-pre'));main.append(lyrics)}
  const downloads=detailSection('다운로드');
  if(j.audio)downloads.append(detailRow('FLAC 오디오',j.duration?Math.round(j.duration)+'초 · 무손실':'무손실',linkButton('저장',j.audio,{download:true,iconName:'download'})));
  if(j.score)downloads.append(detailRow('ABC 악보','텍스트 악보 · 편곡 참고용',linkButton('저장',j.score,{download:true,iconName:'download'})));
  side.append(downloads);
}

function renderImageDetail(j,main,side){
 for(const image of j.images||[]){
  const stage=node('div',undefined,'detail-stage ui-checker'),img=node('img');img.src=url(image.url);img.alt=image.pixelArt?'생성한 도트 초안':'생성한 캐릭터 원화';if(image.pixelArt)img.style.imageRendering='pixelated';stage.append(img);main.append(stage);
  const actions=node('div',undefined,'detail-actions');actions.append(node('span','Seed '+image.seed,'ui-badge'),linkButton('PNG 저장',image.url,{download:true}));
  if(j.sheetLayout)actions.append(linkButton('GIF · 인계용','api/jobs/'+encodeURIComponent(j.id)+'/sheet.gif?source='+encodeURIComponent('image:'+(j.images||[]).indexOf(image)),{download:true}));
  const edit=actionButton('부분 수정');edit.onclick=()=>withBusy(edit,()=>window.transferGeneratedImage(image.url,'image'));actions.append(edit);
  const next=[];
  if(!j.sheetLayout){
   for(const [label,target] of [['동작 만들기','sprite'],['Live2D 만들기','rig']]){const b=actionButton(label);b.onclick=()=>withBusy(b,()=>window.transferGeneratedImage(image.url,target));next.push({kind:target,button:b})}
   if(!image.pixelArt){const b=actionButton('얼굴만 보정');b.onclick=()=>withBusy(b,()=>window.imageFaceRefine.open(j,image));next.push({kind:'face',button:b})}
  }
  if(next.length){if(window.createImageNextActions)main.append(window.createImageNextActions(next));else actions.append(...next.map(entry=>entry.button))}
  if(image.beforeFaceUrl){const b=actionButton('얼굴 전후 비교');b.onclick=()=>window.imageFaceRefine.compare(j,image);actions.append(b)}if(image.warning)main.append(node('p',image.warning,'detail-text'));main.append(actions);
 }
 if(j.metadata)side.append(linkButton('생성 정보 JSON',j.metadata,{download:true}));
 if(j.settings){const details=node('details'),summary=node('summary','생성 세부 설정'),text=node('pre',JSON.stringify(j.settings,null,2));text.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';details.append(summary,text);side.append(details)}
}

async function attachCharacterResult(job){
 const characters=(await api('api/characters')).characters.filter(c=>c.editable);
 if(!characters.length){toast('먼저 캐릭터 작업실에서 묶음을 만들어 주세요.',{action:{label:'작업실 열기',href:'#/characters'}});return}
 const dialog=node('dialog',undefined,'ui-modal'),head=node('div',undefined,'ui-modal__head'),body=node('div',undefined,'ui-modal__body'),foot=node('div',undefined,'ui-modal__foot');head.append(node('h2','캐릭터 묶음에 연결','ui-h3'));
 const choice=node('select',undefined,'ui-input');choice.setAttribute('aria-label','캐릭터 묶음');for(const c of characters)choice.add(new Option(c.name,c.id));
 const role=node('select',undefined,'ui-input');role.setAttribute('aria-label','결과 분류');for(const [v,label] of [['art','원화'],['style','그림체 참고'],['direction','방향'],['motion','동작'],['rig','리깅']])role.add(new Option(label,v));role.value=jobKind(job)==='video'?'motion':jobKind(job)==='rigging'?'rig':'art';
 const direction=node('input',undefined,'ui-input');direction.placeholder='방향 (선택): 정면·오른쪽…';direction.maxLength=40;direction.setAttribute('aria-label','방향');
 const action=node('input',undefined,'ui-input');action.placeholder='동작 (선택): 대기·걷기·공격…';action.maxLength=80;action.setAttribute('aria-label','동작');
 const close=actionButton('취소'),save=actionButton('연결','ui-btn ui-btn--primary');close.onclick=()=>dialog.close();save.onclick=()=>withBusy(save,async()=>{await api('api/characters/'+choice.value+'/jobs',{jobId:job.id,role:role.value,direction:direction.value,action:action.value});dialog.close();toast('캐릭터 묶음에 연결했습니다.',{tone:'success'})});body.style.display='grid';body.style.gap='12px';body.append(choice,role,direction,action);foot.append(close,save);dialog.append(head,body,foot);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();choice.focus();
}
