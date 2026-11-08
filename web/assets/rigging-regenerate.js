'use strict';
// Candidate generation is queued; replacing pixels is a normal undoable editor operation.
const regenerationPanel=document.createElement('div');
regenerationPanel.className='source-controls edit-only';
regenerationPanel.innerHTML='<h3>눈·입·장비 다시 생성</h3><label>다시 만들 파츠<select id="regenerateTarget"></select></label><label>추가 요청 (선택)<input id="regenerateHint" maxlength="500" placeholder="예: 가늘고 자연스럽게 감긴 눈"></label><button id="regeneratePart" type="button">선택 파츠 다시 생성</button><small class="muted">감긴 눈·입은 원본을 참고해 다시 그립니다. 장비(object)는 다시 분리한 결과에서 선택 위치만 가져옵니다. 비교 후 적용하고 저장하면 새 버전이 됩니다.</small><output id="regenerateStatus" aria-live="polite"></output>';
const reviewButton=document.createElement('button');reviewButton.id='reviewRegeneration';reviewButton.type='button';reviewButton.textContent='이전 재생성 진행·후보 확인';reviewButton.hidden=true;regenerationPanel.append(reviewButton);
expressionPanel.after(regenerationPanel);
const candidateDialog=document.createElement('dialog');
candidateDialog.innerHTML='<h2>재생성 결과 비교</h2><p>주변 피부·다른 눈·머리카락이 함께 바뀌지 않았는지 확인하세요. 적용 후에도 저장 전에는 Ctrl+Z로 취소할 수 있습니다.</p><div class="candidate-grid"><figure><figcaption>원본 참고</figcaption><canvas id="candidateSource"></canvas></figure><figure><figcaption>현재 레이어</figcaption><canvas id="candidateBefore"></canvas></figure><figure><figcaption>새 후보</figcaption><canvas id="candidateAfter"></canvas></figure></div><button id="acceptCandidate" type="button">이 파츠에 적용</button> <button id="dismissCandidate" type="button">닫기 · 기존 유지</button>';
candidateDialog.className='rig-candidate-dialog';document.body.append(candidateDialog);
const candidateStyle=document.createElement('style');candidateStyle.textContent='.rig-candidate-dialog{max-width:min(1000px,95vw);max-height:90vh;overflow:auto;background:var(--surface,#20232c);color:inherit;border:1px solid #8885;border-radius:12px;padding:24px}.rig-candidate-dialog::backdrop{background:#0009}.candidate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.candidate-grid figure{margin:0}.candidate-grid canvas{width:100%;height:260px;object-fit:contain;background:repeating-conic-gradient(#7773 0% 25%,#aaa3 0% 50%) 0/16px 16px}.rig-candidate-dialog button{margin-top:16px}#regenerateStatus{font-size:12px;white-space:pre-wrap}@media(max-width:640px){.candidate-grid{grid-template-columns:1fr}.candidate-grid canvas{height:160px}}';document.head.append(candidateStyle);
let regenerationBusy=false,regenerationCandidate=null;
const regenerationStorageKey='rig-regenerate:'+(shareToken||jobId);
function storedRegeneration(){try{return JSON.parse(sessionStorage.getItem(regenerationStorageKey)||'null')}catch{return null}}
function canRegenerate(p){return !p.variantOf&&(p.id.startsWith('eye_close')||['mouth_open','mouth_close'].includes(p.id)||['objects','object'].includes(p.runtimeName)||/^(objects|object_)/.test(p.id))}
function regenerationEndpoint(){return shareToken?`/share/rig/${encodeURIComponent(shareToken)}/rig-edit/regenerate`:`/api/jobs/${encodeURIComponent(jobId)}/rig-edit/regenerate`}
function updateRegeneration(){
 const control=$('regenerateTarget'),old=control.value;control.replaceChildren(...parts.filter(canRegenerate).map(p=>{const option=document.createElement('option');option.value=p.key;option.textContent=p.name;return option}));
 control.value=selected&&canRegenerate(selected)?selected.key:old;if(!control.value&&control.options.length)control.selectedIndex=0;
 $('regeneratePart').disabled=regenerationBusy||saving||readonly||!model||!control.value;
 const part=parts.find(p=>p.key===control.value);$('regenerateHint').disabled=!part||part.kind==='part';
 const stored=storedRegeneration();reviewButton.hidden=!stored||readonly||!model||stored.revision!==model.revision;reviewButton.disabled=regenerationBusy||saving;
}
const regenerateSelection=updateSelection;updateSelection=function(){regenerateSelection();updateRegeneration()};
const regenerateActions=updateActions;updateActions=function(message){regenerateActions(message);updateRegeneration()};
$('regenerateTarget').onchange=()=>{const p=parts.find(p=>p.key===$('regenerateTarget').value);if(p)select(p,false)};
function snapshotLayer(p){return{canvas:cloneCanvas(p.canvas),left:p.left,top:p.top,width:p.width,height:p.height}}
function putCandidate(op){const p=parts.find(p=>p.key===op.layerKey);Object.assign(p,{canvas:cloneCanvas(op.localCanvas),left:op.left,top:op.top,width:op.width,height:op.height});select(p,false)}
async function showCandidate(data){
 const part=parts.find(p=>p.key===data.layerKey);if(!part||data.revision!==model.revision)throw Error('작업 버전이 바뀌어 후보를 적용할 수 없습니다. 다시 생성하세요.');
 const local=await bitmapCanvas(data.imageData,data.width,data.height);regenerationCandidate={...data,localCanvas:local};
 const left=Math.min(part.left,data.left),top=Math.min(part.top,data.top),right=Math.max(part.left+part.width,data.left+data.width),bottom=Math.max(part.top+part.height,data.top+data.height);
 for(const id of ['candidateSource','candidateBefore','candidateAfter']){const c=$(id);c.width=right-left;c.height=bottom-top}
 if(sourceCanvas)$('candidateSource').getContext('2d').drawImage(sourceCanvas,-left,-top);
 $('candidateBefore').getContext('2d').drawImage(part.canvas,part.left-left,part.top-top);
 $('candidateAfter').getContext('2d').drawImage(local,data.left-left,data.top-top);
 candidateDialog.showModal();
}
async function followRegeneration(task){
 regenerationBusy=true;updateRegeneration();
 try{
  for(;;){
   const data=await api(regenerationEndpoint()+'/'+encodeURIComponent(task));$('regenerateStatus').textContent=data.message||'대기 중…';
   if(data.state==='complete'){await showCandidate(data);break}
   if(['error','cancelled'].includes(data.state))throw Error(data.message||'재생성에 실패했습니다. 기존 결과는 유지됩니다.');
   await new Promise(resolve=>setTimeout(resolve,4000));
  }
 }catch(error){$('regenerateStatus').textContent=error.message;status(error.message,true)}
 finally{regenerationBusy=false;updateRegeneration()}
}
$('regeneratePart').onclick=async()=>{
 if(regenerationBusy||saving||readonly||active)return;
 if(history.length){status('수정 내용을 먼저 저장하거나 취소한 뒤 다시 생성하세요.',true);return}
 const layerKey=$('regenerateTarget').value;if(!layerKey)return;
 regenerationBusy=true;updateRegeneration();$('regenerateStatus').textContent='재생성을 요청하는 중…';
 try{const data=await api(regenerationEndpoint(),{revision:model.revision,layerKey,hint:$('regenerateHint').disabled?'':$('regenerateHint').value});try{sessionStorage.setItem(regenerationStorageKey,JSON.stringify({taskId:data.taskId,revision:model.revision}))}catch{}await followRegeneration(data.taskId)}
 catch(error){$('regenerateStatus').textContent=error.message;status(error.message,true)}
 finally{regenerationBusy=false;updateRegeneration()}
};
reviewButton.onclick=()=>{const stored=storedRegeneration();if(stored&&!regenerationBusy)followRegeneration(stored.taskId)};
$('dismissCandidate').onclick=()=>candidateDialog.close();
$('acceptCandidate').onclick=()=>{
 const data=regenerationCandidate;if(!data||saving||readonly)return;
 if(data.revision!==model.revision||history.length){status('후보 생성 후 편집 내용이 바뀌었습니다. 저장하거나 취소하고 다시 생성하세요.',true);return}
 const part=parts.find(p=>p.key===data.layerKey);if(!part||!canRegenerate(part))return;
 const op={kind:'layer_png',layerKey:data.layerKey,left:data.left,top:data.top,width:data.width,height:data.height,imageData:data.imageData,localCanvas:data.localCanvas,before:snapshotLayer(part)};
 history.push(op);redoStack=[];putCandidate(op);candidateDialog.close();updateActions('재생성 후보를 적용했습니다. PSD와 패키지에 저장하면 갤러리·내부 공유에도 반영됩니다.');
};
const regenerateRebuild=rebuild;
rebuild=function(key){
 const first=history.findIndex(op=>op.kind==='layer_png'&&op.layerKey===key);if(first<0){regenerateRebuild(key);return}
 const part=parts.find(p=>p.key===key),replacement=history.findLast(op=>op.kind==='layer_png'&&op.layerKey===key);
 Object.assign(part,{canvas:cloneCanvas(replacement.localCanvas),left:replacement.left,top:replacement.top,width:replacement.width,height:replacement.height});
 const start=history.indexOf(replacement);for(const op of history.slice(start+1))if(op.layerKey===key&&['paint','erase','restore'].includes(op.kind))applyStroke(part,op);render();
};
const regenerateUndo=undo,regenerateRedo=redo;
undo=function(){if(saving||active)return;const op=history.at(-1);if(op?.kind!=='layer_png'){regenerateUndo();return}history.pop();redoStack.push(op);const part=parts.find(p=>p.key===op.layerKey);Object.assign(part,op.before);select(part,false);updateActions()};
redo=function(){if(saving||active)return;const op=redoStack.at(-1);if(op?.kind!=='layer_png'){regenerateRedo();return}redoStack.pop();history.push(op);putCandidate(op);updateActions()};
$('undo').onclick=()=>undo();$('redo').onclick=()=>redo();
