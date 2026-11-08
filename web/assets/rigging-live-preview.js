/* Preview current layer pixels with the same runtime as the exported PSD player. */
(()=>{
 const button=document.createElement('button');button.id='toggleLivePreview';button.type='button';button.textContent='Live2D 미리보기';button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','livePreviewPanel');document.querySelector('.top-actions').prepend(button);
 const views=document.createElement('div');views.className='editor-viewports';views.id='editorViewports';scroll.before(views);views.append(scroll);
 const panel=document.createElement('section');panel.id='livePreviewPanel';panel.className='live-preview-panel';panel.hidden=true;
 panel.innerHTML='<div class="live-preview-head"><strong>Live2D 미리보기</strong><button id="closeLivePreview" type="button" aria-label="Live2D 미리보기 닫기">닫기</button></div><div class="live-preview-controls"><button id="pauseLivePreview" type="button">일시정지</button><button id="refreshLivePreview" type="button">지금 반영</button><label><input id="livePreviewBlink" type="checkbox" checked> 깜박임</label><label><input id="livePreviewTalk" type="checkbox" checked> 입 움직임</label><label><input id="livePreviewIdle" type="checkbox" checked> 대기 동작</label></div><p id="livePreviewStatus" role="status" aria-live="polite">미리보기 준비 중…</p><div id="livePreviewFrame"></div><p class="live-preview-note">저장 전 수정도 반영됩니다. 결과물에 남기려면 상단 저장을 누르세요. 본·타임라인 조작은 포즈 테스트에서 확인합니다.</p>';
 views.append(panel);
 let opened=false,frame=null,timer=null,serial=0,paused=false,lastVariant=null,loading=false;
 function bridge(){return frame?.contentWindow?.spriteEditorPreview}
 function announce(text,state){$('livePreviewStatus').textContent=text;panel.dataset.state=state}
 function options(){bridge()?.options({paused:paused||document.hidden,idle:$('livePreviewIdle').checked,phys:$('livePreviewIdle').checked,blink:$('livePreviewBlink').checked,talk:$('livePreviewTalk').checked})}
 function snapshot(){
  if(!model)throw Error('레이어를 먼저 불러와 주세요.');
  const children=parts.filter(p=>!p.variantOf).map(part=>{
   const variant=selected?.variantOf===part.key?selected:null,p=variant||part;
   const slot=part.kind==='expression'&&(['eyeClose','eyeClose2','mouthOpen','mouthClose'].includes(part.fade)||part.id.startsWith('eye_close')||['mouth_open','mouth_close'].includes(part.id));
   return{name:part.runtimeName||part.id,left:p.left,top:p.top,right:p.left+p.width,bottom:p.top+p.height,
     hidden:!part.visible&&!slot,opacity:1,blendMode:'normal',imageData:p.canvas.getContext('2d').getImageData(0,0,p.width,p.height)};
  });
  return{width:canvas.width,height:canvas.height,children};
 }
 async function refresh(){
  clearTimeout(timer);if(!opened||!model||saving)return;
  if(loading){announce('레이어를 불러오는 중…','loading');schedule();return}
  if(active){schedule();return}
  const mark=++serial;announce('현재 수정 내용을 반영하는 중…','loading');
  try{
   const deadline=Date.now()+15000;
   while(!bridge()){if(!opened||mark!==serial)return;if(Date.now()>deadline)throw Error('미리보기를 불러오지 못했어요. 지금 반영을 눌러 다시 시도하세요.');await new Promise(resolve=>setTimeout(resolve,100));}
   if(!opened||mark!==serial)return;
   await bridge().load(snapshot());if(!opened||mark!==serial)return;options();
   announce(selected?.variantOf?'선택한 표정 차분 미리보기 · 적용/저장은 별도입니다.':history.length?'자동 반영됨 · 저장 전 수정 포함':`저장본 v${model.revision+1} · 편집하면 자동 반영`,'ready');
  }catch(error){if(opened&&mark===serial){const message=/[\u3040-\u30ff]/.test(error.message)?'레이어 크기·메모리 또는 표시 가능한 픽셀을 확인하세요.':error.message;announce('미리보기 실패 · '+message,'error');}}
 }
 function schedule(){if(!opened)return;clearTimeout(timer);timer=setTimeout(refresh,650)}
 function toggle(value){
  opened=value;serial++;clearTimeout(timer);panel.hidden=!opened;views.classList.toggle('live-preview-open',opened);button.setAttribute('aria-expanded',String(opened));
  if(!opened){frame?.remove();frame=null;return}
  if(matchMedia('(max-width: 860px)').matches){document.body.classList.add('panel-collapsed');$('panelToggle')?.setAttribute('aria-expanded','false')}
  announce('Live2D를 여는 중…','loading');frame=document.createElement('iframe');frame.id='livePreviewPlayer';frame.title='현재 레이어의 Live2D 움직임';frame.src=shareToken?`/share/rig/${encodeURIComponent(shareToken)}/player?editor=1`:'/rigging-player/index.html?editor=1';$('livePreviewFrame').append(frame);refresh();
 }
 button.onclick=()=>toggle(!opened);$('closeLivePreview').onclick=()=>toggle(false);$('refreshLivePreview').onclick=refresh;
 $('pauseLivePreview').onclick=()=>{paused=!paused;$('pauseLivePreview').textContent=paused?'재생':'일시정지';options()};
 for(const id of ['livePreviewBlink','livePreviewTalk','livePreviewIdle'])$(id).onchange=options;
 document.addEventListener('visibilitychange',options);
 const actions=updateActions;updateActions=function(...args){actions(...args);schedule()};
 const selection=updateSelection;updateSelection=function(...args){selection(...args);const next=selected?.variantOf?selected.key:null;if(next!==lastVariant){lastVariant=next;schedule()}};
 const editorLoad=load;load=async function(...args){loading=true;try{await editorLoad(...args)}finally{loading=false;schedule()}};
})();
