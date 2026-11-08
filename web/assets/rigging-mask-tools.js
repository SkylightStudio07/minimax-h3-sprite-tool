/* Expression masking: common editor shortcuts, scoped erase, reversible edits. */
(()=>{
 const viewport=$('canvasScroll'),stage=$('canvasStage'),names={eyeLeft:'화면 왼쪽 눈',eyeRight:'화면 오른쪽 눈',eyebrowLeft:'화면 왼쪽 눈썹',eyebrowRight:'화면 오른쪽 눈썹',mouth:'입'};
 const labels=Object.keys(names),undoStack=[],redoStack=[];
 let region='eyeLeft',hand=false,space=false,pan=null,beforeStroke=null,pointer=null;
 const oldSetTool=setTool,oldSetup=setupCanvas;
 const toolbar=document.createElement('div');toolbar.className='mask-commandbar';
 toolbar.innerHTML='<div class="mask-tool-switch" role="group" aria-label="마스킹 도구"><button id="maskBrush" type="button" aria-pressed="true" title="브러시 (B)">브러시 <kbd>B</kbd></button><button id="maskErase" type="button" aria-pressed="false" title="선택 영역 지우개 (E)">지우개 <kbd>E</kbd></button><button id="maskHand" type="button" aria-pressed="false" title="화면 이동 (H) · Space를 누른 채 드래그">이동 <kbd>H</kbd></button></div><output id="maskToolStatus" role="status" aria-live="polite"></output><div class="mask-view-actions"><button id="maskFit" type="button" title="화면에 맞추기 (Ctrl+0)">화면 맞춤</button><button id="maskOverlay" type="button" aria-pressed="true" title="마스크 표시 전환 (Q)">마스크 표시 <kbd>Q</kbd></button><details class="mask-shortcuts"><summary>단축키</summary><p><kbd>B</kbd> 브러시 · <kbd>E</kbd> 지우개 · <kbd>H</kbd> 화면 이동<br><kbd>1</kbd> 왼쪽 눈 · <kbd>2</kbd> 오른쪽 눈 · <kbd>3</kbd><kbd>4</kbd> 눈썹 · <kbd>5</kbd> 입<br><kbd>[</kbd> <kbd>]</kbd> 브러시 크기 · <kbd>Space</kbd> 누르고 드래그 / 휠 버튼 드래그로 이동<br><kbd>Ctrl Z</kbd> 취소 · <kbd>Ctrl Shift Z</kbd> / <kbd>Ctrl Y</kbd> 다시 실행<br><kbd>Ctrl 휠</kbd> 확대 · <kbd>Ctrl 0</kbd> 화면 맞춤 · <kbd>Ctrl 1</kbd> 100%<br><kbd>Q</kbd> 마스크 표시/숨기기</p></details></div>';
 $('maskWork').querySelector('.mask-layout').before(toolbar);
 const hint=document.createElement('p');hint.className='muted mask-nav-hint';hint.textContent='영역을 고르고 칠하세요. 지우개는 선택한 영역에만 적용됩니다. Space를 누른 채 드래그하면 화면이 이동합니다.';toolbar.after(hint);
 const redo=document.createElement('button');redo.id='maskRedo';redo.type='button';redo.textContent='다시 실행';redo.title='Ctrl+Shift+Z / Ctrl+Y';$('undo').after(redo);$('undo').title='실행 취소 (Ctrl+Z)';
 const clear=document.createElement('button');clear.id='maskClearRegion';clear.type='button';clear.textContent='선택 영역 지우기';$('clearMasks').before(clear);$('clearMasks').textContent='전체 지우기';$('clearMasks').title='모든 눈 입력 방식의 마스크를 지웁니다. Ctrl+Z로 복원할 수 있어요.';
 const historyBar=document.createElement('div');historyBar.className='mask-historybar';historyBar.setAttribute('role','group');historyBar.setAttribute('aria-label','마스크 실행 취소와 지우기');historyBar.append($('undo'),redo,clear,$('clearMasks'));hint.before(historyBar);
 const opacity=document.createElement('label');opacity.className='range';opacity.innerHTML='<span>마스크 투명도</span><output id="maskOpacityValue">34%</output><input id="maskOpacity" type="range" min="10" max="80" value="34" aria-label="마스크 표시 투명도">';$('brush').parentElement.after(opacity);
 document.querySelector('[data-tool="erase"]').hidden=true;
 labels.forEach((label,i)=>{const button=document.querySelector(`[data-tool="${label}"]`);button.title=`${names[label]} (${i+1})`;const key=document.createElement('kbd');key.textContent=String(i+1);button.append(key)});
 const cursor=document.createElement('div');cursor.id='maskBrushCursor';cursor.hidden=true;stage.append(cursor);
 const scratch=document.createElement('canvas'),sc=scratch.getContext('2d');
 viewport.tabIndex=0;viewport.setAttribute('aria-label','눈·입 마스킹 캔버스. B 브러시, E 지우개, Space 이동, Ctrl+휠 확대');
 $('zoom').min='10';$('zoom').max='800';$('brush').max='256';

 function update(){
  document.querySelectorAll('[data-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===region)));
  $('maskBrush').setAttribute('aria-pressed',String(!hand&&tool!=='erase'));$('maskErase').setAttribute('aria-pressed',String(!hand&&tool==='erase'));$('maskHand').setAttribute('aria-pressed',String(hand));
  const label=names[region]+((region==='eyeLeft'||region==='eyeRight')?(currentEyeMode()==='area'?' 영역':' 감은 선'):'');
  $('maskToolStatus').textContent=`${label} · ${hand||space?'화면 이동':tool==='erase'?'선택 영역 지우개':'브러시'} · ${$('brush').value}px`;
  $('maskToolStatus').style.setProperty('--mask-color',colors[region]);
  $('undo').disabled=!undoStack.length;redo.disabled=!redoStack.length;
  const enabled=Boolean(sourceImage);clear.disabled=!enabled;$('clearMasks').disabled=!strokes.length;
  maskCanvas.style.cursor=pan||hand||space?(pan?'grabbing':'grab'):'crosshair';
  if(hand||space)cursor.hidden=true;
 }
 setTool=function(next){
  const size=$('brush').value,same=next===region||next==='erase';
  if(next!=='erase')region=next;
  hand=false;oldSetTool(next);
  if(same){$('brush').value=size;$('brushValue').value=size+'px'}
  update();
 };
 function chooseRegion(next){const erase=tool==='erase',moving=hand,size=$('brush').value;setTool(next);if(erase){$('brush').value=size;setTool('erase')}if(moving){hand=true;update()}}
 labels.forEach(label=>{document.querySelector(`[data-tool="${label}"]`).onclick=()=>{chooseRegion(label);setStatus(names[label]+' 영역을 선택했습니다.')}});
 $('maskBrush').onclick=()=>setTool(region);$('maskErase').onclick=()=>setTool('erase');$('maskHand').onclick=()=>{hand=true;update()};
 function visibleStroke(stroke,label){return (stroke.tool===label||(stroke.tool==='erase'&&(!stroke.target||stroke.target===label)))&&(!(label==='eyeLeft'||label==='eyeRight')||!stroke.eyeMode||stroke.eyeMode===currentEyeMode())}
 renderMasks=function(){
  maskCtx.clearRect(0,0,maskCanvas.width,maskCanvas.height);previewCtx.clearRect(0,0,previewCanvas.width,previewCanvas.height);
  if(scratch.width!==maskCanvas.width||scratch.height!==maskCanvas.height){scratch.width=maskCanvas.width;scratch.height=maskCanvas.height}
  const previewing=currentEyeMode()==='closed-stroke'&&$('eyePreviewToggle').checked;
  for(const label of labels){
   if(eyeSkipped(label)||label.startsWith('eyebrow')&&!$('preserveOriginalEyebrows').checked)continue;
   sc.clearRect(0,0,scratch.width,scratch.height);
   const isEye=label==='eyeLeft'||label==='eyeRight';
   for(const stroke of strokes)if(visibleStroke(stroke,label))drawStroke(sc,stroke,stroke.tool==='erase'?'#000':isEye&&previewing?'#3c2632':colors[label]);
   (isEye&&previewing?previewCtx:maskCtx).drawImage(scratch,0,0);
  }
  update();
 };
 function record(before){undoStack.push({before,after:strokes.slice()});if(undoStack.length>50)undoStack.shift();redoStack.length=0;update()}
 function finish(cancel=false){
  if(activeStroke){const before=beforeStroke;activeStroke=null;beforeStroke=null;if(cancel)strokes=before;else record(before);renderMasks()}
  if(pointer!==null&&maskCanvas.hasPointerCapture(pointer))maskCanvas.releasePointerCapture(pointer);
  pointer=null;pan=null;update();
 }
 function undoMask(){finish();const op=undoStack.pop();if(op){redoStack.push(op);strokes=op.before.slice();renderMasks()}update()}
 function redoMask(){finish();const op=redoStack.pop();if(op){undoStack.push(op);strokes=op.after.slice();renderMasks()}update()}
 $('undo').onclick=undoMask;redo.onclick=redoMask;
 clear.onclick=()=>{finish();const before=strokes.slice();strokes=strokes.filter(s=>!visibleStroke(s,region));if(strokes.length!==before.length)record(before);renderMasks()};
 $('clearMasks').onclick=()=>{finish();if(strokes.length){const before=strokes.slice();strokes=[];record(before);renderMasks()}};
 function showCursor(event){
  if(hand||space||!sourceImage){cursor.hidden=true;return}
  const point=pointOf(event),zoom=Number($('zoom').value)/100,size=Number($('brush').value)*zoom;
  cursor.style.width=cursor.style.height=Math.max(2,size)+'px';cursor.style.left=point.x*zoom+'px';cursor.style.top=point.y*zoom+'px';cursor.style.borderColor=tool==='erase'?'#fff':colors[region];cursor.classList.toggle('is-eraser',tool==='erase');cursor.hidden=false;
 }
 maskCanvas.onpointerdown=event=>{
  if(!sourceImage||![0,1].includes(event.button))return;
  event.preventDefault();viewport.focus({preventScroll:true});maskCanvas.setPointerCapture(event.pointerId);pointer=event.pointerId;
  if(hand||space||event.button===1){pan={x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};cursor.hidden=true;update();return}
  beforeStroke=strokes.slice();activeStroke={tool,size:Number($('brush').value),target:tool==='erase'?region:undefined,eyeMode:(region==='eyeLeft'||region==='eyeRight')?currentEyeMode():null,points:[pointOf(event)]};strokes.push(activeStroke);renderMasks();showCursor(event);
 };
 maskCanvas.onpointermove=event=>{if(pan){viewport.scrollLeft=pan.left-(event.clientX-pan.x);viewport.scrollTop=pan.top-(event.clientY-pan.y);return}showCursor(event);if(activeStroke){activeStroke.points.push(pointOf(event));renderMasks()}};
 maskCanvas.onpointerup=()=>finish();maskCanvas.onpointercancel=()=>finish(true);maskCanvas.onpointerleave=()=>{cursor.hidden=true};maskCanvas.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault()});

 function zoomTo(value,anchor){
  const rect=viewport.getBoundingClientRect(),x=anchor?anchor.x-rect.left:viewport.clientWidth/2,y=anchor?anchor.y-rect.top:viewport.clientHeight/2;
  const old=Number($('zoom').value)/100,px=(viewport.scrollLeft+x)/old,py=(viewport.scrollTop+y)/old;
  $('zoom').value=Math.max(10,Math.min(800,value));applyZoom();const next=Number($('zoom').value)/100;viewport.scrollLeft=px*next-x;viewport.scrollTop=py*next-y;cursor.hidden=true;
 }
 function fit(){if(!sourceImage)return;zoomTo(Math.floor(Math.min((viewport.clientWidth-16)/imageCanvas.width,(viewport.clientHeight-16)/imageCanvas.height,1)*100));viewport.scrollLeft=viewport.scrollTop=0}
 changeZoom=delta=>zoomTo(Number($('zoom').value)+delta);$('zoom').oninput=()=>{applyZoom();cursor.hidden=true};$('zoomReset').onclick=()=>zoomTo(100);$('maskFit').onclick=fit;
 viewport.addEventListener('wheel',event=>{if(!(event.ctrlKey||event.metaKey))return;event.preventDefault();event.stopImmediatePropagation();zoomTo(Number($('zoom').value)+(event.deltaY<0?25:-25),{x:event.clientX,y:event.clientY})},{passive:false,capture:true});
 $('brush').oninput=()=>{$('brushValue').value=$('brush').value+'px';update()};
 $('maskOpacity').oninput=()=>{maskCanvas.style.opacity=$('maskOverlay').getAttribute('aria-pressed')==='true'?Number($('maskOpacity').value)/100:0;$('maskOpacityValue').value=$('maskOpacity').value+'%'};
 $('maskOverlay').onclick=()=>{const visible=$('maskOverlay').getAttribute('aria-pressed')!=='true';$('maskOverlay').setAttribute('aria-pressed',String(visible));$('maskOverlay').textContent=visible?'마스크 표시 · Q':'마스크 숨김 · Q';maskCanvas.style.opacity=visible?Number($('maskOpacity').value)/100:0;previewCanvas.style.opacity=visible?1:0};
 setupCanvas=function(image){finish(true);undoStack.length=redoStack.length=0;oldSetup(image);region='eyeLeft';hand=false;oldSetTool('eyeLeft');$('maskOverlay').setAttribute('aria-pressed','true');$('maskOverlay').textContent='마스크 표시 · Q';maskCanvas.style.opacity=Number($('maskOpacity').value)/100;previewCanvas.style.opacity=1;requestAnimationFrame(fit);update()};
 const oldClearImage=$('clearImage').onclick;$('clearImage').onclick=()=>{finish(true);oldClearImage();undoStack.length=redoStack.length=0;imageCtx.clearRect(0,0,imageCanvas.width,imageCanvas.height);renderMasks();cursor.hidden=true};
 function typing(target){return Boolean(target.closest('input,textarea,select,[contenteditable="true"]'))}
 document.addEventListener('keydown',event=>{
  if(!sourceImage||$('maskPane').hidden||$('maskWork').hidden||typing(event.target)||event.altKey)return;
  const key=event.key.toLowerCase(),mod=event.ctrlKey||event.metaKey;
  if(event.code==='Space'){if(event.target.closest('button,a,summary'))return;event.preventDefault();space=true;update();return}
  if(mod&&key==='z'){event.preventDefault();event.shiftKey?redoMask():undoMask();return}
  if(mod&&key==='y'){event.preventDefault();redoMask();return}
  if(mod&&['+','=','-','0','1'].includes(key)){event.preventDefault();if(key==='0')fit();else if(key==='1')zoomTo(100);else changeZoom(key==='-'?-25:25);return}
  if(mod)return;
  if(key==='b'){event.preventDefault();setTool(region)}else if(key==='e'){event.preventDefault();setTool('erase')}else if(key==='h'){event.preventDefault();hand=true;update()}else if(key==='q'){event.preventDefault();$('maskOverlay').click()}else if(key==='['||key===']'){event.preventDefault();$('brush').value=Math.max(2,Math.min(Number($('brush').max),Number($('brush').value)+(key==='['?-4:4)));$('brush').oninput()}else if(/^[1-5]$/.test(key)){const label=labels[Number(key)-1],button=document.querySelector(`[data-tool="${label}"]`);if(!button.disabled){event.preventDefault();chooseRegion(label)}}
 });
 document.addEventListener('keyup',event=>{if(event.code==='Space'){space=false;update()}});window.addEventListener('blur',()=>{space=false;finish(true);cursor.hidden=true});
 for(const id of ['leftAbsent','rightAbsent','preserveOriginalEyebrows'])$(id).addEventListener('change',()=>{renderMasks();update()});
 update();
})();
