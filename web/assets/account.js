/* 계정 설정 (#/my/settings): profile, password, theme, completion notices, usage, shared links.
 * Loaded before team.html's inline script; runs only when the shell calls openSettings() or notifyDone(). */

const NOTIFY_KEY='sprite-notify';
const notifySupported=()=>'Notification' in window&&window.isSecureContext;
function notifyEnabled(){try{return localStorage.getItem(NOTIFY_KEY)==='1'&&notifySupported()&&Notification.permission==='granted'}catch(error){return false}}

/* Browser notification for a finished job while the tab is in the background. */
function notifyDone(j,name){
  if(!document.hidden||!notifyEnabled())return;
  const notice=new Notification('Sprite Lab · 작업 완료',{body:name,tag:'sprite-job-'+j.id});
  notice.onclick=()=>{window.focus();location.hash='#/jobs/'+encodeURIComponent(j.id);notice.close()};
}

function applyUser(){
  $('who').textContent=me.name;
  $('whoRole').textContent=me.role==='admin'?'관리자':'팀원';
  $('whoAvatar').textContent=(me.name||'?').slice(0,1);
  $('adminNav').hidden=me.role!=='admin';
}

let accountBound=false,summaryTicket=0;
function openSettings(){
  bindAccount();
  $('profileName').value=me.name;$('profileUsername').textContent=me.username||'';$('profileRole').textContent=me.role==='admin'?'관리자':'팀원';
  $('pwUsername').value=me.username||'';
  syncThemeChoice();syncNotifyChoice();loadAccountSummary();
}

function syncThemeChoice(){
  const theme=document.documentElement.dataset.theme;
  document.querySelectorAll('#themeChoice [data-theme-value]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeValue===theme)));
}
function syncNotifyChoice(){
  const toggle=$('notifySwitch'),hint=$('notifyHint');
  if(!notifySupported()){toggle.checked=false;toggle.disabled=true;hint.textContent=window.isSecureContext?'이 브라우저는 알림을 지원하지 않아요.':'알림은 HTTPS 주소로 접속했을 때만 쓸 수 있어요.';return}
  toggle.disabled=Notification.permission==='denied';toggle.checked=notifyEnabled();
  hint.textContent=Notification.permission==='denied'?'브라우저에서 이 사이트의 알림을 차단했어요. 주소창의 사이트 설정에서 허용으로 바꿔 주세요.':'다른 탭을 보고 있을 때 내 작업이 끝나면 알려 드려요. 이 브라우저에만 저장됩니다.';
}

function bindAccount(){
  if(accountBound)return;accountBound=true;
  $('profileForm').onsubmit=event=>{
    event.preventDefault();
    withBusy(event.submitter,async()=>{const d=await api('api/me/profile',{name:$('profileName').value});me=d.user;applyUser();toast('이름을 바꿨습니다.',{tone:'success'})});
  };
  $('passwordForm').onsubmit=event=>{
    event.preventDefault();
    const error=$('passwordError');error.hidden=true;
    if($('newPassword').value!==$('confirmPassword').value){error.textContent='새 비밀번호 두 칸이 서로 다릅니다.';error.hidden=false;return}
    withBusy(event.submitter,async()=>{
      try{await api('api/me/password',{currentPassword:$('currentPassword').value,newPassword:$('newPassword').value});event.target.reset();$('pwUsername').value=me.username||'';toast('비밀번호를 바꿨습니다. 다른 기기에서는 다시 로그인해야 합니다.',{tone:'success'})}
      catch(failure){error.textContent=failure.message;error.hidden=false}
    });
  };
  document.querySelectorAll('#themeChoice [data-theme-value]').forEach(b=>b.onclick=()=>SpriteUI.theme.set(b.dataset.themeValue));
  document.addEventListener('themechange',syncThemeChoice);
  $('notifySwitch').onchange=async()=>{
    const toggle=$('notifySwitch');
    if(!toggle.checked){try{localStorage.setItem(NOTIFY_KEY,'0')}catch(error){}syncNotifyChoice();return}
    const permission=Notification.permission==='granted'?'granted':await Notification.requestPermission();
    try{localStorage.setItem(NOTIFY_KEY,permission==='granted'?'1':'0')}catch(error){}
    if(permission==='granted')toast('작업 완료 알림을 켰습니다.',{tone:'success'});
    syncNotifyChoice();
  };
}

async function loadAccountSummary(){
  const ticket=++summaryTicket;
  try{
    const d=await api('api/me/summary');
    if(ticket!==summaryTicket)return;
    $('usageSprite').textContent=d.counts.video;$('usageRig').textContent=d.counts.rigging;$('usageMusic').textContent=d.counts.music;$('usageImage').textContent=d.counts.image||0;
    $('usageActive').textContent=`${d.active} / ${d.activeLimit}`;
    $('usageActiveBar').style.setProperty('--value',Math.min(100,d.active/d.activeLimit*100)+'%');
    drawShareRows(d.shares);
    $('publicSection').hidden=!d.publicLive2d.length;
    $('publicRows').replaceChildren(...d.publicLive2d.map(item=>detailRow(item.title,'공개 · '+fmtDate(item.updated)+' 갱신',linkButton('열기',item.url,{newTab:true,iconName:'external'}),linkButton('결과','#/jobs/'+encodeURIComponent(item.jobId),{cls:'ui-btn ui-btn--ghost ui-btn--sm'}))));
  }catch(error){if(ticket===summaryTicket)toast(error.message,{tone:'danger'})}
}

function drawShareRows(shares){
  const list=$('shareRows');
  if(!shares.length){empty(list,'공유 중인 내부 링크가 없어요. 리깅 결과 상세의 "공유"에서 만들 수 있습니다.');return}
  list.replaceChildren(...shares.map(share=>{
    const row=node('div',undefined,'share-row'),thumb=node('a',undefined,'share-thumb ui-checker'),text=node('div',undefined,'detail-row__text'),actions=node('div',undefined,'detail-row__actions');
    thumb.href='#/jobs/'+encodeURIComponent(share.jobId);thumb.setAttribute('aria-label','결과 보기');
    if(share.composite){const img=node('img');img.src=url(versioned(share.composite,share.rigRevision));img.alt='';img.loading='lazy';img.onerror=()=>img.remove();thumb.append(img)}
    const title=node('a',share.title||'2D 리깅 캐릭터');title.href=thumb.href;
    text.append(title,node('span',fmtDate(share.created)+' 공유 시작 · 링크가 있으면 누구나 보고 편집할 수 있어요'));
    const copy=actionButton('복사','ui-btn ui-btn--sm','link');
    copy.onclick=()=>withBusy(copy,async()=>{await navigator.clipboard.writeText(url(share.url));toast('공유 링크를 복사했습니다.',{tone:'success'})});
    const revoke=actionButton('해제','ui-btn ui-btn--danger ui-btn--sm');
    revoke.onclick=()=>withBusy(revoke,async()=>{
      if(!await uiDialog({title:'이 공유 링크를 해제할까요?',body:'이 링크로 들어오던 팀원은 더 이상 열 수 없습니다. 다시 공유하면 새 링크가 만들어집니다.',confirmLabel:'링크 해제',danger:true}))return;
      await api('api/shares/'+encodeURIComponent(share.token)+'/revoke',{});toast('공유 링크를 해제했습니다.',{tone:'success'});loadAccountSummary();
    });
    actions.append(linkButton('열기',share.url,{newTab:true,iconName:'external'}),copy,revoke);
    row.append(thumb,text,actions);return row;
  }));
}
