'use strict';
// Variants are editable archives; Apply copies their pixels into an existing animation slot.
const expressionPanel=document.createElement('div');
expressionPanel.className='source-controls edit-only';
expressionPanel.innerHTML='<h3>표정 차분</h3><label>바꿀 눈·입·눈썹<select id="expressionTarget"></select></label><label>새 차분 이름<input id="expressionName" maxlength="60" placeholder="감은 눈 / 웃는 입"></label><button id="newExpression">빈 차분 만들기</button><button id="copyExpression">현재 파츠 복제</button><label>색상 <input id="inkColor" type="color" value="#29202b"></label><label><input id="expressionOnion" type="checkbox" checked> 원래 파츠를 25%로 참고</label><button id="expressionPNG">투명 PNG 가져오기</button><input id="expressionFile" type="file" accept="image/png" hidden><button id="applyExpression">선택 차분을 움직임에 적용</button><small class="muted">차분을 선택하면 해당 파츠를 교체해 미리봅니다. 적용 후 저장하세요. 감은 눈은 좌우 슬롯을 각각 작업합니다. PNG는 전체 캔버스 또는 차분 크기로 준비하세요.</small>';
$('mergeControls').after(expressionPanel);
document.querySelector('.right').style.overflowY='auto';
const inkTool=document.createElement('button');inkTool.id='paintTool';inkTool.className='tool edit-only';inkTool.title='색상 브러시 (P)';inkTool.innerHTML='<strong>P</strong><span>그리기</span>';document.querySelector('.tools').append(inkTool);
function expressionTargets(){return parts.filter(p=>!p.variantOf&&(p.kind==='expression'||/eye|mouth|brow/.test(p.id)))}
function updateExpressionPanel(){
 const select=$('expressionTarget'),old=select.value;select.replaceChildren(...expressionTargets().map(p=>{const o=document.createElement('option');o.value=p.key;o.textContent=p.name;return o}));
 select.value=selected?.variantOf||((selected&&expressionTargets().includes(selected))?selected.key:old);if(!select.value&&select.options.length)select.selectedIndex=0;
 for(const id of ['expressionPNG','applyExpression'])$(id).disabled=saving||!selected?.variantOf||history.some(op=>op.kind==='variant_apply');
}
const originalSelection=updateSelection;updateSelection=function(){originalSelection();updateExpressionPanel()};
const originalLayerList=drawLayerList;drawLayerList=function(){originalLayerList();for(const part of parts.filter(p=>p.variantOf)){const row=document.querySelector(`[data-layer-key="${part.key}"]`),check=row?.querySelector('input');if(check){check.disabled=true;check.title='보관 차분: 레이어를 클릭하면 해당 파츠 대신 미리봅니다.'}}};
const originalActions=updateActions;updateActions=function(message){originalActions(message);for(const id of ['newExpression','copyExpression'])$(id).disabled=saving||readonly||!model;updateExpressionPanel()};
function drawExpressionPart(part){
 if(part.variantOf)return;
 const target=!comparing&&selected?.variantOf?parts.find(p=>p.key===selected.variantOf):null;
 if(target&&part!==target){
  if(target.id.startsWith('eye_close')&&(part.id==='eye_open_original'||/^(eyewhite|irides|eyelash)/.test(part.id))){if(part.visible){ctx.save();ctx.beginPath();ctx.rect(0,0,canvas.width,canvas.height);ctx.rect(selected.left,selected.top,selected.width,selected.height);ctx.clip('evenodd');ctx.drawImage(part.canvas,part.left,part.top);ctx.restore()}return}
  if(target.id.startsWith('eye_open')&&part.id.startsWith('eye_close'))return;
  if(target.id==='mouth_open'&&part.id==='mouth_close'||target.id==='mouth_close'&&part.id==='mouth_open')return;
 }
 const variant=!comparing&&selected?.variantOf===part.key?selected:null;
 if(!variant){if(part.visible)ctx.drawImage(comparing?part.saved:part.canvas,part.left,part.top);return}
 if($('expressionOnion').checked){ctx.save();ctx.globalAlpha=.25;ctx.drawImage(part.canvas,part.left,part.top);ctx.restore()}
 ctx.drawImage(variant.canvas,variant.left,variant.top);
}
$('expressionOnion').onchange=render;
function createVariant(copy){
 if(saving||readonly||active)return;const target=parts.find(p=>p.key===$('expressionTarget').value);if(!target)return;
 if(history.some(op=>op.kind==='variant_apply')){status('차분 적용 후에는 먼저 저장하거나 적용을 취소하세요.',true);return}
 const name=$('expressionName').value.trim()||(copy?'원본 복제':'새 차분'),id='variant_'+Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join(''),left=Math.max(0,target.left-24),top=Math.max(0,target.top-24),width=Math.min(canvas.width,target.left+target.width+24)-left,height=Math.min(canvas.height,target.top+target.height+24)-top;
 const blank=document.createElement('canvas');blank.width=width;blank.height=height;if(copy)blank.getContext('2d').drawImage(target.canvas,target.left-left,target.top-top);
 const part={id,key:'expression:'+id,kind:'expression',variantOf:target.key,name:'차분 · '+name,sourceLayerName:'차분 · '+name,runtimeName:'차분 · '+name,left,top,width,height,visible:false,saved:cloneCanvas(blank),generated:cloneCanvas(blank),canvas:cloneCanvas(blank)};
 const op={kind:'variant_create',targetKey:target.key,id,name,copy,localPart:part};parts.push(part);history.push(op);redoStack=[];select(part,false);setTool('paint',false);updateActions('차분을 만들었습니다. P로 그리고 E로 지운 뒤, 움직임에 적용하고 저장하세요.');
}
$('newExpression').onclick=()=>createVariant(false);$('copyExpression').onclick=()=>createVariant(true);
const oldTool=setTool;setTool=function(next,announce=true){oldTool(next,announce&&next!=='paint');inkTool.classList.toggle('active',tool==='paint');if(next==='paint'&&announce)status('색상 브러시: 차분을 선택하고 그리세요. P · 지우개 E · 취소 Ctrl+Z')};inkTool.onclick=()=>setTool('paint');
document.addEventListener('keydown',event=>{if(!['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName)&&!event.ctrlKey&&!event.metaKey&&event.key.toLowerCase()==='p'&&!readonly){event.preventDefault();setTool('paint')}});
const oldDown=canvas.onpointerdown;canvas.onpointerdown=event=>{if(history.some(op=>op.kind==='variant_apply')&&tool!=='move'&&!space){status('차분 적용 뒤에는 먼저 저장하거나 Ctrl+Z로 적용을 취소하세요.',true);return}if(tool==='paint'&&!selected?.variantOf){status('새 차분을 만들거나 기존 차분을 선택하세요.',true);return}oldDown(event);if(active?.kind==='paint')active.color=$('inkColor').value};
const oldRebuild=rebuild;rebuild=function(key){const part=parts.find(p=>p.key===key);if(!part?.variantOf){oldRebuild(key);return}part.canvas=cloneCanvas(part.saved);for(const op of history){if(op.layerKey!==key)continue;if(op.kind==='variant_png'){part.canvas=cloneCanvas(op.localCanvas)}else if(['paint','erase','restore'].includes(op.kind))applyStroke(part,op)}render()};
function applyVariant(op){const variant=parts.find(p=>p.key===op.layerKey),target=parts.find(p=>p.key===variant.variantOf);if(!op.before)op.before={canvas:target.canvas,left:target.left,top:target.top,width:target.width,height:target.height};target.canvas=cloneCanvas(variant.canvas);for(const k of ['left','top','width','height'])target[k]=variant[k];selected=variant;drawLayerList();updateSelection();render()}
$('applyExpression').onclick=()=>{if(!selected?.variantOf||saving||active)return;const pixels=selected.canvas.getContext('2d').getImageData(0,0,selected.width,selected.height).data;if(!pixels.some((v,i)=>i%4===3&&v)){status('먼저 차분을 그리거나 PNG로 가져오세요.',true);return}const op={kind:'variant_apply',layerKey:selected.key};applyVariant(op);history.push(op);redoStack=[];updateActions('차분을 기존 움직임 슬롯에 적용했습니다. 저장하면 PSD·갤러리·내부 공유에 반영됩니다.')};
$('expressionPNG').onclick=()=>{if(!saving&&selected?.variantOf)$('expressionFile').click()};
$('expressionFile').onchange=async()=>{const file=$('expressionFile').files[0],part=selected;$('expressionFile').value='';if(!file||!part?.variantOf)return;if(file.type!=='image/png'||file.size>20*1024*1024){status('20MB 이하 투명 PNG를 선택하세요.',true);return}const revision=model.revision;try{const bitmap=await createImageBitmap(file);if(!((bitmap.width===part.width&&bitmap.height===part.height)||(bitmap.width===canvas.width&&bitmap.height===canvas.height))){bitmap.close();throw Error(`PNG 크기는 ${canvas.width}×${canvas.height} 또는 ${part.width}×${part.height}여야 합니다.`)}const target=document.createElement('canvas');target.width=part.width;target.height=part.height;target.getContext('2d').drawImage(bitmap,bitmap.width===canvas.width?-part.left:0,bitmap.height===canvas.height?-part.top:0);bitmap.close();if(saving||model.revision!==revision||!parts.includes(part))return;const op={kind:'variant_png',layerKey:part.key,imageData:target.toDataURL('image/png'),localCanvas:target};history.push(op);redoStack=[];rebuild(part.key);updateActions('PNG를 차분으로 가져왔습니다. 움직임에 적용하고 저장하세요.')}catch(error){status(error.message,true)}};
const oldUndo=undo,oldRedo=redo;
undo=function(){if(active||saving)return;const op=history.at(-1);if(!op||!['variant_create','variant_apply','variant_png'].includes(op.kind)){oldUndo();return}history.pop();redoStack.push(op);if(op.kind==='variant_create'){parts=parts.filter(p=>p!==op.localPart);if(selected===op.localPart)selected=null}else if(op.kind==='variant_apply'){const variant=parts.find(p=>p.key===op.layerKey),target=parts.find(p=>p.key===variant.variantOf);Object.assign(target,op.before);selected=variant}else rebuild(op.layerKey);drawLayerList();updateSelection();render();updateActions()};
redo=function(){if(active||saving)return;const op=redoStack.at(-1);if(!op||!['variant_create','variant_apply','variant_png'].includes(op.kind)){oldRedo();return}redoStack.pop();if(op.kind==='variant_create'){parts.push(op.localPart);selected=op.localPart}else if(op.kind==='variant_apply')applyVariant(op);history.push(op);if(op.kind==='variant_png')rebuild(op.layerKey);drawLayerList();updateSelection();render();updateActions()};
$('undo').onclick=()=>undo();$('redo').onclick=()=>redo();
function serializeEditOperation(op){if(op.kind==='merge')return{kind:op.kind,sourceLayerKey:op.sourceLayerKey,targetLayerKey:op.targetLayerKey};const {localPart,localCanvas,before,...plain}=op;return plain}
