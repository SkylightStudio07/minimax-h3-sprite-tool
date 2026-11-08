/* Signed-out main page. Public Live2D characters run through the bundled player in OBS mode
 * (no UI, transparent): one large in the hero, one small in the 2D rigging tool card.
 * Page-wide mouse movement is forwarded so the characters follow the cursor.
 * Loaded before team.html's inline script; initLanding() runs from showAuth(). */

let landingBound=false,landingItems=[],heroIndex=0,showcaseIndex=0,toolIndex=0,heroPlayer=null,toolPlayer=null,rigCardVisible=false,pendingPointer=null;
const livePlayers=[];
const liveAllowed=()=>!matchMedia('(prefers-reduced-motion: reduce)').matches&&!navigator.connection?.saveData;
const narrowLayout=()=>matchMedia('(max-width: 860px)').matches;

function initLanding(){
  if(!landingBound){landingBound=true;bindLanding()}
  loadLandingData();
}

function openAuth(mode){
  registering=mode==='register'||setup;renderAuth();$('authMessage').textContent='';
  closeLandingSheet();
  if(!$('authDialog').open)$('authDialog').showModal();
  $('username').focus();
}
function closeLandingSheet(){$('landingSheet').hidden=true;$('landingMenu').setAttribute('aria-expanded','false')}

/* ------------------------------------------------------------- live players */
/* A preview image plus an iframe running /live2d/<token>/player?obs=1 inside `stage` (.l-live).
 * The image shows until the player has parsed the PSD, then the two cross-fade. */
function createLivePlayer(stage,frame){
  const loading=node('div',undefined,'l-loading'),bar=node('span',undefined,'l-loading-bar');
  loading.setAttribute('role','status');loading.hidden=true;bar.append(node('i'));loading.append(bar,node('span','','l-loading-label'));
  stage.append(loading);
  const player={stage,frame,loading,token:null,request:0,paused:false,active:false,step:0,progress:0,lastStatus:'',timer:0};
  frame.addEventListener('load',()=>watchLivePlayer(player));
  livePlayers.push(player);
  return player;
}
/* The player reports its stages (download, layers, decode, cleanup, rig) as #dropStatus text but no
 * byte progress, so the bar jumps on each new stage and creeps toward the next one in between. */
const LOAD_STEPS=[['플레이어 준비 중',6],['PSD 받는 중',28],['레이어 확인 중',46],['이미지 펼치는 중',64],['가장자리 정리 중',80],['움직임 만드는 중',93]];
function setLoadStep(player,step){
  player.step=Math.min(step,LOAD_STEPS.length-1);
  player.loading.querySelector('.l-loading-label').textContent=LOAD_STEPS[player.step][0];
  player.progress=Math.max(player.progress,LOAD_STEPS[player.step][1]-12);
  drawLoad(player);
}
function drawLoad(player){player.loading.style.setProperty('--p',player.progress.toFixed(1)+'%')}
function creepLoad(player){
  clearInterval(player.timer);
  player.timer=setInterval(()=>{
    if(player.stage.classList.contains('is-live')||player.loading.hidden){clearInterval(player.timer);return}
    const ceiling=LOAD_STEPS[player.step][1];player.progress+=(ceiling-player.progress)*.08;drawLoad(player);
  },300);
}
function loadLivePlayer(player,item){
  player.stage.classList.remove('is-live');player.paused=false;
  const img=player.stage.querySelector('img');img.src=url(item.preview);img.alt=item.title;
  if(!liveAllowed()){player.token=null;player.loading.hidden=true;player.frame.removeAttribute('src');return}
  player.token=item.token;player.progress=0;player.lastStatus='';player.loading.hidden=false;player.loading.classList.remove('is-error');
  setLoadStep(player,0);creepLoad(player);
  player.frame.src=url(`live2d/${encodeURIComponent(item.token)}/player?obs=1`);
}
function watchLivePlayer(player){
  const token=player.token,started=performance.now(),request=++player.request;
  if(!token)return;
  if(player.step<1)setLoadStep(player,1);
  const poll=()=>{
    if(request!==player.request||token!==player.token)return;
    let doc=null;try{doc=player.frame.contentDocument}catch(error){return}
    const status=(doc?.getElementById('dropStatus')?.textContent||'').trim();
    if(/エラー|오류|에러/.test(status)){failLoad(player);return}
    if(status&&status!==player.lastStatus){if(player.lastStatus)setLoadStep(player,player.step+1);player.lastStatus=status}
    if(doc?.getElementById('drop')?.classList.contains('hidden')&&doc.getElementById('cv')){
      const style=doc.createElement('style');
      style.textContent='#viewControls,#stageLabel,#appStatus,#fps,#rigInfo{display:none!important}html,body{background:transparent!important}';
      doc.head.append(style);
      const mouse=doc.getElementById('tgMouse');if(mouse&&!mouse.classList.contains('on'))mouse.click();
      player.progress=100;drawLoad(player);
      player.stage.classList.add('is-live');syncLivePause(player);return;
    }
    if(performance.now()-started<30000)setTimeout(poll,200);else failLoad(player);
  };
  poll();
}
/* Keep the still preview and say so; never leave a bar running forever. */
function failLoad(player){
  clearInterval(player.timer);player.loading.classList.add('is-error');
  player.loading.querySelector('.l-loading-label').textContent='움직임을 불러오지 못해 정지 이미지로 보여 드려요';
  setTimeout(()=>{player.loading.hidden=true},4000);
}
/* Render only while a player is wanted on screen; the bundled player has a single pause toggle. */
function setLiveActive(player,active){player.active=active;syncLivePause(player)}
function syncLivePause(player){
  if(!player.stage.classList.contains('is-live'))return;
  const pause=!player.active;if(pause===player.paused)return;
  try{player.frame.contentDocument.getElementById('btnPause')?.click();player.paused=pause}catch(error){}
}
function forwardPointer(){
  const event=pendingPointer;pendingPointer=null;if(!event)return;
  const clamp=v=>Math.max(-1,Math.min(1,v));
  for(const player of livePlayers){
    if(!player.active||!player.stage.classList.contains('is-live'))continue;
    try{
      const frame=player.frame,canvas=frame.contentDocument?.getElementById('cv');if(!canvas)continue;
      const box=frame.getBoundingClientRect(),inner=canvas.getBoundingClientRect();
      // Map the whole page onto the canvas so the gaze follows the cursor anywhere, but never past the edges.
      const nx=clamp((event.clientX-(box.left+box.width/2))/(innerWidth/2)),ny=clamp((event.clientY-(box.top+box.height*.35))/(innerHeight/2));
      canvas.dispatchEvent(new frame.contentWindow.MouseEvent('mousemove',{clientX:inner.left+(nx+1)/2*inner.width,clientY:inner.top+(ny+1)/2*inner.height,bubbles:true}));
    }catch(error){/* player navigated away */}
  }
}

function bindLanding(){
  document.querySelectorAll('[data-auth-open]').forEach(button=>button.addEventListener('click',()=>openAuth(button.dataset.authOpen)));
  $('authClose').onclick=()=>$('authDialog').close();
  $('authDialog').addEventListener('click',event=>{if(event.target===$('authDialog'))$('authDialog').close()});
  $('landingMenu').onclick=()=>{const open=$('landingSheet').hidden;$('landingSheet').hidden=!open;$('landingMenu').setAttribute('aria-expanded',String(open))};
  $('landingSheet').addEventListener('click',event=>{if(event.target.closest('a'))closeLandingSheet()});

  // Over the dark hero the nav is transparent and light; past it, it turns solid in the page theme.
  const nav=$('landingNav'),onScroll=()=>{const solid=scrollY>8;nav.classList.toggle('is-solid',solid);nav.classList.toggle('tone-ink',!solid)};
  addEventListener('scroll',onScroll,{passive:true});onScroll();
  const links=[...document.querySelectorAll('#landingNav .l-links a')];
  const sectionObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)links.forEach(a=>a.setAttribute('aria-current',String(a.hash==='#'+entry.target.id)))},{rootMargin:'-45% 0px -50% 0px'});
  document.querySelectorAll('.landing section[id]').forEach(section=>sectionObserver.observe(section));

  const revealObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){entry.target.classList.add('is-in');revealObserver.unobserve(entry.target)}},{threshold:.12});
  document.querySelectorAll('[data-reveal]').forEach(el=>revealObserver.observe(el));

  heroPlayer=createLivePlayer($('heroStage'),$('heroPlayer'));
  toolPlayer=createLivePlayer($('toolRigMedia'),$('toolRigPlayer'));
  new IntersectionObserver(([entry])=>setLiveActive(heroPlayer,entry.isIntersecting)).observe($('heroStage'));
  new IntersectionObserver(([entry])=>{rigCardVisible=entry.isIntersecting;syncToolPlayer()},{threshold:.4}).observe($('toolRigMedia'));
  addEventListener('pointermove',event=>{if(event.pointerType!=='mouse')return;const first=!pendingPointer;pendingPointer=event;if(first)requestAnimationFrame(forwardPointer)},{passive:true});
  $('heroDots').addEventListener('click',event=>{const b=event.target.closest('button');if(b)setHeroCharacter(Number(b.dataset.index))});

  $('toolPrev').onclick=()=>setTool(toolIndex-1);$('toolNext').onclick=()=>setTool(toolIndex+1);
  document.querySelectorAll('.l-tool').forEach((card,index)=>card.addEventListener('click',event=>{if(index!==toolIndex&&!narrowLayout()&&!event.target.closest('a')){event.preventDefault();setTool(index)}}));
  $('toolDots').addEventListener('click',event=>{const b=event.target.closest('button');if(b)setTool(Number(b.dataset.index))});
  $('toolTrack').addEventListener('keydown',event=>{if(event.key==='ArrowLeft')setTool(toolIndex-1);if(event.key==='ArrowRight')setTool(toolIndex+1)});
  setTool(0);

  // 캐릭터 원화 card cycles one character through several styles while it is in view.
  const styleImages=[...document.querySelectorAll('#toolImageMedia img')];let styleIndex=0,styleVisible=false;
  new IntersectionObserver(([entry])=>{styleVisible=entry.isIntersecting},{threshold:.3}).observe($('toolImageMedia'));
  if(styleImages.length>1&&!matchMedia('(prefers-reduced-motion: reduce)').matches)setInterval(()=>{
    if(!styleVisible||document.hidden)return;
    styleImages[styleIndex].classList.remove('is-on');styleIndex=(styleIndex+1)%styleImages.length;
    styleImages[styleIndex].classList.add('is-on');$('toolStyleChip').textContent=styleImages[styleIndex].dataset.label;
  },2200);
  $('charThumbs').addEventListener('click',event=>{const b=event.target.closest('button');if(b)setShowcase(Number(b.dataset.index))});
}

async function loadLandingData(){
  try{
    const [live,gallery]=await Promise.all([api('api/public-live2d'),api('api/gallery?size=1')]);
    landingItems=live.items;
    $('statLive').textContent=live.items.length;$('statGallery').textContent=gallery.total;
    buildHero();buildShowcase();buildToolMedia(gallery.jobs);
  }catch(error){/* the static page still works without data */}
}

/* ----------------------------------------------------------------- hero */
function buildHero(){
  const dots=$('heroDots');
  dots.replaceChildren(...landingItems.map((item,index)=>{const b=node('button');b.type='button';b.dataset.index=index;b.setAttribute('aria-label',item.title+' 보기');return b}));
  dots.hidden=landingItems.length<2;
  $('heroStage').hidden=!landingItems.length;
  if(landingItems.length)setHeroCharacter(0);
}
function setHeroCharacter(index){
  heroIndex=(index+landingItems.length)%landingItems.length;
  const item=landingItems[heroIndex];
  $('heroCharName').textContent=item.title;$('heroCharLink').href=url(item.url);
  $('heroDots').querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-current',String(i===heroIndex)));
  loadLivePlayer(heroPlayer,item);
}

/* -------------------------------------------------------------- showcase */
function buildShowcase(){
  $('characters').hidden=!landingItems.length;
  $('charThumbs').replaceChildren(...landingItems.map((item,index)=>{const b=node('button'),img=node('img');b.type='button';b.dataset.index=index;b.setAttribute('aria-label',item.title);img.src=url(item.preview);img.alt='';img.loading='lazy';b.append(img);return b}));
  if(landingItems.length)setShowcase(0);
}
function setShowcase(index){
  showcaseIndex=index;const item=landingItems[index],art=$('charArt');
  art.classList.add('is-entering');
  requestAnimationFrame(()=>{art.src=url(item.preview);art.alt=item.title;art.onload=()=>art.classList.remove('is-entering');if(art.complete)art.classList.remove('is-entering')});
  $('charName').textContent=item.title;$('charLink').href=url(item.url);
  $('charUpdated').textContent=fmtDate(item.updated)+' 공개';
  $('charThumbs').querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-current',String(i===index)));
}

/* ----------------------------------------------------------------- tools */
function setTool(index){
  const cards=[...document.querySelectorAll('.l-tool')],count=cards.length;
  toolIndex=(index+count)%count;
  cards.forEach((card,i)=>{
    let offset=i-toolIndex;if(offset>count/2)offset-=count;if(offset<-count/2)offset+=count;
    card.style.setProperty('--offset',offset);card.style.setProperty('--depth',Math.abs(offset));
    card.setAttribute('aria-current',String(offset===0));
    const video=card.querySelector('video');if(video){if(offset===0||narrowLayout())video.play().catch(()=>{});else video.pause()}
  });
  $('toolDots').querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-current',String(i===toolIndex)));
  syncToolPlayer();
}
/* The small rigging player loads the first time its card is wanted, then plays only while wanted. */
function syncToolPlayer(){
  if(!toolPlayer)return;
  const item=landingItems[1]||landingItems[0];
  const rigIndex=[...document.querySelectorAll('.l-tool')].findIndex(card=>card.contains($('toolRigMedia')));
  const wanted=rigCardVisible&&(narrowLayout()||toolIndex===rigIndex);
  if(wanted&&item&&!toolPlayer.frame.getAttribute('src')&&liveAllowed())loadLivePlayer(toolPlayer,item);
  setLiveActive(toolPlayer,wanted);
}
function buildToolMedia(jobs){
  const sprite=jobs.find(j=>j.video||j.loopVideo);
  if(sprite){
    const video=node('video');video.muted=true;video.loop=true;video.playsInline=true;video.preload='metadata';
    if(sprite.poster)video.poster=url(sprite.poster);video.src=url(sprite.loopVideo||sprite.video);
    $('toolSpriteMedia').replaceChildren(video);setTool(toolIndex);
  }
  const rigItem=landingItems[1]||landingItems[0];
  if(rigItem){const img=$('toolRigMedia').querySelector('img');img.src=url(rigItem.preview);img.alt=rigItem.title;$('toolRigMedia').classList.add('has-preview')}
}
