'use strict';
// Rest geometry is persistent. Pose offsets are temporary and never alter source pixels.
const boneState={mode:'layers',rig:null,selected:'head',pose:{},poseUndo:[],poseRedo:[],drag:null,cache:new Map()};
const coreBones=new Set(['hips','spine','chest','neck','head','shoulder_l','arm_l','hand_l','shoulder_r','arm_r','hand_r','leg_l','knee_l','foot_l','leg_r','knee_r','foot_r']);
const boneLabels={hips:'골반',spine:'허리',chest:'가슴',neck:'목',head:'머리',shoulder_l:'왼쪽 어깨',arm_l:'왼쪽 팔꿈치',hand_l:'왼쪽 손목',shoulder_r:'오른쪽 어깨',arm_r:'오른쪽 팔꿈치',hand_r:'오른쪽 손목',leg_l:'왼쪽 허벅지',knee_l:'왼쪽 무릎',foot_l:'왼쪽 발목',leg_r:'오른쪽 허벅지',knee_r:'오른쪽 무릎',foot_r:'오른쪽 발목'};
const cloneRig=value=>JSON.parse(JSON.stringify(value));
function boneLabel(name){if(boneLabels[name])return boneLabels[name];const hair=parts.find(p=>name==='hair_'+p.id||name==='hair_tip_'+p.id);if(hair){const title={'front hair':'앞머리','back hair':'뒷머리'}[hair.name]||hair.name;return title+(name.startsWith('hair_tip_')?' 끝':' 뿌리')}const match=name.match(/^control_(\d+)(_tip)?$/);return match?`조작점 ${match[1]} ${match[2]?'끝':'뿌리'}`:name}
function selectBonePart(part){select(part)}
function rigConfig(){return{schemaVersion:1,bones:cloneRig(boneState.rig.bones),bindings:cloneRig(boneState.rig.bindings),mesh:{columns:9,rows:9,maxInfluences:2}}}
const boneBar=document.createElement('div');boneBar.className='toolbar';boneBar.setAttribute('aria-label','편집 모드');
boneBar.innerHTML='<button id="layerMode">레이어 편집</button><button id="rigMode" class="edit-only">본 위치·연결</button><button id="poseMode">포즈 테스트</button><label><input id="boneMesh" type="checkbox"> 메시 보기</label><label><input id="boneNames" type="checkbox" checked> 본 이름</label><button id="resetPose">포즈 초기화</button><button id="boneV2" class="edit-only">저장본으로 Unity V2 생성</button>';
document.querySelector('.workspace').prepend(boneBar);document.querySelector('.workspace').style.gridTemplateRows='auto auto 1fr';
const bonePanel=document.createElement('section');bonePanel.className='panel bone-panel';bonePanel.hidden=true;
bonePanel.innerHTML='<h2>본 · 파츠 연결</h2><label>선택 본<select id="boneSelect" style="width:100%"></select></label><div id="boneAffected" style="max-height:100px;overflow:auto;margin-top:8px"></div><div id="restFields" class="source-controls edit-only"><label>부모 본<select id="boneParent"></select></label><label>X <input id="boneX" type="number" step="1"></label><label>Y <input id="boneY" type="number" step="1"></label><button id="applyBonePoint">좌표·연결 적용</button><button id="removeBone">선택 조작점 삭제</button><button id="addBoneControl">선택 파츠에 유연 조작점 추가</button><div id="boneBindings"></div></div><div id="poseFields" class="source-controls"><label>선택 본 회전 <output id="boneAngleValue">0°</output><input id="boneAngle" type="range" min="-180" max="180" value="0"></label><button id="poseUndo">포즈 취소</button><button id="poseRedo">포즈 다시 실행</button></div><p id="boneHint" class="muted" style="margin-top:8px"></p>';
document.querySelector('.right').prepend(bonePanel);
const boneStyle=document.createElement('style');boneStyle.textContent='.source-controls[hidden]{display:none!important}.bone-editing .tools .edit-only{display:none}.bone-editing .right>.panel:not(.bone-panel) .source-controls,.bone-editing #mergeControls,.bone-editing .range{display:none!important}#boneBindings{max-height:190px;overflow:auto}.bone-panel select,.bone-panel input[type=number]{max-width:100%;width:100%}';document.head.append(boneStyle);
for(const id of ['boneNames','boneMesh'])$(id).onchange=()=>render();
function matrixMultiply(a,b){return[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]]}
function transformPoint(m,x,y){return{x:m[0]*x+m[2]*y+m[4],y:m[1]*x+m[3]*y+m[5]}}
function inversePoint(m,x,y){const det=m[0]*m[3]-m[1]*m[2],dx=x-m[4],dy=y-m[5];return{x:(m[3]*dx-m[2]*dy)/det,y:(m[0]*dy-m[1]*dx)/det}}
function boneWorld(){
 const map=new Map(),byName=new Map(boneState.rig.bones.map(b=>[b.name,b]));
 function visit(b){if(map.has(b.name))return map.get(b.name);const parent=byName.get(b.parent),p=boneState.mode==='pose'?boneState.pose[b.name]||{}:{},angle=(p.angle||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),local=[c,s,-s,c,b.x-(parent?.x||0)+(p.dx||0),b.y-(parent?.y||0)+(p.dy||0)];const world=parent?matrixMultiply(visit(parent),local):local;map.set(b.name,world);return world}
 for(const bone of boneState.rig.bones)visit(bone);return map;
}
function skinWeights(key,x,y){const names=boneState.rig.bindings[key]||['head'];const candidates=boneState.rig.bones.map((b,i)=>({i,d:Math.hypot(x-b.x,y-b.y),name:b.name})).filter(c=>names.includes(c.name)).sort((a,b)=>a.d-b.d).slice(0,2);const total=candidates.reduce((n,c)=>n+1/Math.max(4,c.d),0);return candidates.map(c=>({i:c.i,w:(1/Math.max(4,c.d))/total}))}
function meshFor(part){
 let cached=boneState.cache.get(part.key);if(cached&&cached.width===part.width&&cached.height===part.height&&cached.left===part.left&&cached.top===part.top)return cached;
 const vertices=[],indices=[],cols=9,rows=9;
 for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){const sx=part.width*col/(cols-1),sy=part.height*row/(rows-1),x=part.left+sx,y=part.top+sy;vertices.push({sx,sy,x,y,weights:skinWeights(part.key,x,y)})}
 for(let row=0;row<rows-1;row++)for(let col=0;col<cols-1;col++){const a=row*cols+col,b=a+1,c=a+cols,d=c+1;indices.push(a,b,c,b,d,c)}
 cached={vertices,indices,width:part.width,height:part.height,left:part.left,top:part.top};boneState.cache.set(part.key,cached);return cached;
}
function posedVertices(mesh,world){return mesh.vertices.map(v=>{let x=0,y=0;for(const influence of v.weights){const bone=boneState.rig.bones[influence.i],p=transformPoint(world.get(bone.name),v.x-bone.x,v.y-bone.y);x+=p.x*influence.w;y+=p.y*influence.w}return{...v,x,y}})}
function drawSkin(part,mesh,vertices){
 for(let i=0;i<mesh.indices.length;i+=3){const [a,b,c]=mesh.indices.slice(i,i+3).map(index=>vertices[index]);const ux=b.sx-a.sx,uy=b.sy-a.sy,vx=c.sx-a.sx,vy=c.sy-a.sy,den=ux*vy-uy*vx;if(Math.abs(den)<1e-8)continue;const dx=b.x-a.x,dy=b.y-a.y,ex=c.x-a.x,ey=c.y-a.y,A=(dx*vy-ex*uy)/den,B=(dy*vy-ey*uy)/den,C=(ex*ux-dx*vx)/den,D=(ey*ux-dy*vx)/den;
  ctx.save();ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.lineTo(c.x,c.y);ctx.closePath();ctx.clip();ctx.setTransform(A,B,C,D,a.x-A*a.sx-C*a.sy,a.y-B*a.sx-D*a.sy);ctx.drawImage(part.canvas,0,0);ctx.restore();
 }
}
function drawMesh(mesh,vertices){ctx.save();ctx.lineWidth=1/currentZoom();ctx.strokeStyle='#73d5e466';ctx.beginPath();for(let i=0;i<mesh.indices.length;i+=3){const [a,b,c]=mesh.indices.slice(i,i+3).map(index=>vertices[index]);ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.lineTo(c.x,c.y);ctx.closePath()}ctx.stroke();ctx.restore()}
const layerRender=render;render=function(){
 if(!boneState.rig||boneState.mode==='layers'){layerRender();return}
 const world=boneWorld(),isPosed=boneState.mode==='pose'&&Object.values(boneState.pose).some(p=>Math.abs(p.dx||0)+Math.abs(p.dy||0)+Math.abs(p.angle||0)>1e-8);
 ctx.clearRect(0,0,canvas.width,canvas.height);
 for(const part of parts){if(!part.visible||part.variantOf)continue;const mesh=meshFor(part),vertices=isPosed?posedVertices(mesh,world):mesh.vertices;if(isPosed)drawSkin(part,mesh,vertices);else ctx.drawImage(part.canvas,part.left,part.top);if($('boneMesh').checked&&(part===selected||!selected))drawMesh(mesh,vertices)}
 const zoom=currentZoom();ctx.save();ctx.lineWidth=2/zoom;ctx.font=`${12/zoom}px system-ui`;
 for(const bone of boneState.rig.bones){const m=world.get(bone.name),p={x:m[4],y:m[5]},parent=world.get(bone.parent);ctx.strokeStyle=bone.name===boneState.selected?'#ffe29d':'#63ddcd';if(parent){ctx.beginPath();ctx.moveTo(parent[4],parent[5]);ctx.lineTo(p.x,p.y);ctx.stroke()}ctx.beginPath();ctx.arc(p.x,p.y,(bone.name===boneState.selected?7:5)/zoom,0,Math.PI*2);ctx.fillStyle=bone.name===boneState.selected?'#ffe29d':'#fff';ctx.fill();ctx.stroke();if($('boneNames').checked){ctx.lineWidth=3/zoom;ctx.strokeStyle='#10151c';const name=boneLabel(bone.name);ctx.strokeText(name,p.x+9/zoom,p.y-8/zoom);ctx.fillStyle='#edf9ff';ctx.fillText(name,p.x+9/zoom,p.y-8/zoom);ctx.lineWidth=2/zoom}}
 ctx.restore();
};
function descendants(name){const out=new Set([name]);let changed=true;while(changed){changed=false;for(const b of boneState.rig.bones)if(out.has(b.parent)&&!out.has(b.name)){out.add(b.name);changed=true}}return out}
function updateBoneUI(){
 bonePanel.hidden=boneState.mode==='layers'||!boneState.rig;
 for(const [id,mode] of [['layerMode','layers'],['rigMode','rest'],['poseMode','pose']]){$(id).classList.toggle('primary',mode===boneState.mode);$(id).disabled=saving||!model||mode!=='layers'&&!boneState.rig}
 $('resetPose').hidden=boneState.mode!=='pose';$('boneMesh').disabled=!boneState.rig;$('boneV2').disabled=saving||history.length>0||readonly||!model;
 if(!boneState.rig)return;
 const bone=boneState.rig.bones.find(b=>b.name===boneState.selected)||boneState.rig.bones[0];boneState.selected=bone.name;
 const select=$('boneSelect');select.replaceChildren(...boneState.rig.bones.map(b=>{const o=document.createElement('option');o.value=b.name;o.textContent=boneLabel(b.name);return o}));select.value=bone.name;
 const affected=$('boneAffected');affected.replaceChildren();const affectedTitle=document.createElement('small');affectedTitle.textContent='직접 연결된 파츠';affected.append(affectedTitle);for(const part of parts.filter(p=>(boneState.rig.bindings[p.key]||[]).includes(bone.name))){const button=document.createElement('button');button.textContent=part.name;button.style.cssText='padding:3px 6px;margin:3px;font-size:12px';button.onclick=()=>selectBonePart(part);affected.append(button)}
 const blocked=descendants(bone.name),parent=$('boneParent');parent.replaceChildren(...boneState.rig.bones.filter(b=>!blocked.has(b.name)).map(b=>{const o=document.createElement('option');o.value=b.name;o.textContent=boneLabel(b.name);return o}));parent.value=bone.parent||'';parent.disabled=bone.name==='hips';
 $('boneX').value=Math.round(bone.x*100)/100;$('boneY').value=Math.round(bone.y*100)/100;$('removeBone').disabled=coreBones.has(bone.name)||saving;
 $('addBoneControl').disabled=!selected||selected.kind!=='part'||saving;
 $('restFields').hidden=boneState.mode!=='rest';$('poseFields').hidden=boneState.mode!=='pose';const angle=boneState.pose[bone.name]?.angle||0;$('boneAngle').value=angle;$('boneAngleValue').textContent=Math.round(angle)+'°';
 $('poseUndo').disabled=!boneState.poseUndo.length;$('poseRedo').disabled=!boneState.poseRedo.length;
 $('boneHint').textContent=boneState.mode==='rest'?'점을 드래그하면 원래 관절 위치만 바뀝니다. 레이어 목록에서 파츠를 선택해 연결을 조정하고 저장하세요.':'점을 드래그하거나 회전해 파츠 변형을 테스트합니다. 자식 본도 따라 움직입니다. 포즈는 저장·원본 픽셀에 반영되지 않습니다.';
 const root=$('boneBindings');root.replaceChildren();if(selected&&!selected.variantOf){const title=document.createElement('strong');title.textContent=selected.name+' · 따를 본';root.append(title);for(const b of boneState.rig.bones){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=(boneState.rig.bindings[selected.key]||[]).includes(b.name);input.disabled=selected.kind==='expression'||saving;input.onchange=()=>{const before=rigConfig(),names=boneState.rig.bindings[selected.key]||[];const next=input.checked?[...names,b.name]:names.filter(n=>n!==b.name);if(!next.length||next.length>16){input.checked=!input.checked;status('파츠 연결은 1~16개 본으로 지정하세요.',true);return}boneState.rig.bindings[selected.key]=next;recordRig(before)};label.style.display='block';label.append(input,' '+(boneLabel(b.name)));root.append(label)}}
}
function recordRig(before){const config=rigConfig();history.push({kind:'rig_config',before,config});redoStack=[];boneState.cache.clear();boneState.pose={};updateBoneUI();render();updateActions('본 위치·파츠 연결 수정 · 저장 전');}
function setBoneMode(mode){
 if(saving||active||boneState.drag||mode==='rest'&&readonly)return;
 if(mode!=='layers'&&history.some(op=>!['rig_config','rig_animation'].includes(op.kind))){status('레이어·표정 편집을 먼저 저장한 뒤 본 모드로 이동하세요.',true);return}
 boneState.mode=mode;document.body.classList.toggle('bone-editing',mode!=='layers');if(mode!=='layers'){setTool('move',false);sourceOverlay=false;if(selected?.variantOf)selected=null}updateSelection();updateBoneUI();render();status(mode==='layers'?'레이어 편집 모드':mode==='rest'?'본 위치·연결: 관절을 드래그하고 저장하세요.':'포즈 테스트: 관절 드래그와 회전을 시험하세요. 원본은 바뀌지 않습니다.');
}
$('layerMode').onclick=()=>setBoneMode('layers');$('rigMode').onclick=()=>setBoneMode('rest');$('poseMode').onclick=()=>setBoneMode('pose');
$('boneSelect').onchange=()=>{boneState.selected=$('boneSelect').value;updateBoneUI();render()};
$('applyBonePoint').onclick=()=>{if(saving||readonly||boneState.mode!=='rest')return;const bone=boneState.rig.bones.find(b=>b.name===boneState.selected),x=Number($('boneX').value),y=Number($('boneY').value);if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||y<0||x>canvas.width||y>canvas.height){status('관절 좌표는 캔버스 안에 입력하세요.',true);return}const before=rigConfig();bone.x=x;bone.y=y;if(bone.name!=='hips')bone.parent=$('boneParent').value;recordRig(before)};
$('addBoneControl').onclick=()=>{if(!selected||selected.kind!=='part'||saving||readonly)return;const before=rigConfig(),names=new Set(boneState.rig.bones.map(b=>b.name));if(names.size>94){status('본은 96개까지 추가할 수 있습니다.',true);return}let n=1;while(names.has('control_'+n))n++;const name='control_'+n,parent=(boneState.rig.bindings[selected.key]||[]).includes('head')?'head':/leg|bottom|skirt/.test(selected.id)?'hips':'chest';boneState.rig.bones.push({name,parent,x:selected.left+selected.width*.5,y:selected.top+selected.height*.2,length:selected.height*.65},{name:name+'_tip',parent:name,x:selected.left+selected.width*.5,y:selected.top+selected.height*.85,length:selected.height*.15});boneState.rig.bindings[selected.key]=[parent,name,name+'_tip'];boneState.selected=name+'_tip';recordRig(before)};
$('removeBone').onclick=()=>{if(coreBones.has(boneState.selected)||saving||readonly)return;const removed=descendants(boneState.selected);if([...removed].some(n=>coreBones.has(n))){status('기본 전신 본이 연결되어 있어 삭제할 수 없습니다.',true);return}const before=rigConfig();boneState.rig.bones=boneState.rig.bones.filter(b=>!removed.has(b.name));for(const key of Object.keys(boneState.rig.bindings)){const names=boneState.rig.bindings[key].filter(n=>!removed.has(n));boneState.rig.bindings[key]=names.length?names:['head']}boneState.selected='head';recordRig(before)};
function recordPose(before){boneState.poseUndo.push(before);boneState.poseRedo=[];updateBoneUI();render()}
let angleBefore=null;
$('boneAngle').oninput=()=>{if(boneState.mode!=='pose')return;if(!angleBefore)angleBefore=cloneRig(boneState.pose);boneState.pose[boneState.selected]={...boneState.pose[boneState.selected],angle:Number($('boneAngle').value)};$('boneAngleValue').textContent=$('boneAngle').value+'°';render()};
$('boneAngle').onchange=()=>{if(boneState.mode!=='pose')return;const before=angleBefore||cloneRig(boneState.pose);angleBefore=null;boneState.pose[boneState.selected]={...boneState.pose[boneState.selected],angle:Number($('boneAngle').value)};recordPose(before)};
function poseUndo(){if(!boneState.poseUndo.length)return;boneState.poseRedo.push(cloneRig(boneState.pose));boneState.pose=boneState.poseUndo.pop();updateBoneUI();render()}
function poseRedo(){if(!boneState.poseRedo.length)return;boneState.poseUndo.push(cloneRig(boneState.pose));boneState.pose=boneState.poseRedo.pop();updateBoneUI();render()}
$('poseUndo').onclick=poseUndo;$('poseRedo').onclick=poseRedo;$('resetPose').onclick=()=>{if(Object.keys(boneState.pose).length){const before=cloneRig(boneState.pose);boneState.pose={};recordPose(before)}};
const boneLayerDown=canvas.onpointerdown,boneLayerMove=canvas.onpointermove,boneLayerUp=canvas.onpointerup;
canvas.onpointerdown=event=>{
 if(boneState.mode==='layers'||space||event.button===1){boneLayerDown(event);return}if(saving||event.button!==0||!boneState.rig)return;
 const point=canvasPoint(event),world=boneWorld();let best=null,distance=14/currentZoom();for(const bone of boneState.rig.bones){const m=world.get(bone.name),d=Math.hypot(point.x-m[4],point.y-m[5]);if(d<distance){best=bone;distance=d}}
 if(!best){const found=hitTest(point);if(found)select(found);return}boneState.selected=best.name;
 if(readonly&&boneState.mode==='rest')return;boneState.drag={name:best.name,before:boneState.mode==='rest'?rigConfig():cloneRig(boneState.pose),pointerId:event.pointerId};event.preventDefault();canvas.setPointerCapture(event.pointerId);updateBoneUI();render();
};
canvas.onpointermove=event=>{
 if(!boneState.drag){boneLayerMove(event);return}const point=canvasPoint(event),bone=boneState.rig.bones.find(b=>b.name===boneState.drag.name);
 if(boneState.mode==='rest'){bone.x=Math.max(0,Math.min(canvas.width,point.x));bone.y=Math.max(0,Math.min(canvas.height,point.y));boneState.cache.clear()}
 else{const parent=boneState.rig.bones.find(b=>b.name===bone.parent),world=boneWorld(),local=parent?inversePoint(world.get(parent.name),point.x,point.y):point;boneState.pose[bone.name]={...boneState.pose[bone.name],dx:local.x-(bone.x-(parent?.x||0)),dy:local.y-(bone.y-(parent?.y||0))}}
 render();
};
function finishBone(event){if(!boneState.drag){boneLayerUp(event);return}const drag=boneState.drag;boneState.drag=null;if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);if(event.type==='pointercancel'){if(boneState.mode==='rest')boneState.rig=drag.before;else boneState.pose=drag.before;boneState.cache.clear();updateBoneUI();render();return}if(boneState.mode==='rest'){if(JSON.stringify(drag.before)!==JSON.stringify(rigConfig()))recordRig(drag.before)}else if(JSON.stringify(drag.before)!==JSON.stringify(boneState.pose))recordPose(drag.before);updateBoneUI()}
canvas.onpointerup=finishBone;canvas.onpointercancel=finishBone;
const boneLayerUndo=undo,boneLayerRedo=redo;
undo=function(){if(boneState.drag||saving)return;if(boneState.mode==='pose'){poseUndo();return}const op=history.at(-1);if(op?.kind==='rig_config'){history.pop();redoStack.push(op);boneState.rig=cloneRig(op.before);boneState.cache.clear();updateBoneUI();render();updateActions()}else boneLayerUndo()};
redo=function(){if(boneState.drag||saving)return;if(boneState.mode==='pose'){poseRedo();return}const op=redoStack.at(-1);if(op?.kind==='rig_config'){redoStack.pop();history.push(op);boneState.rig=cloneRig(op.config);boneState.cache.clear();updateBoneUI();render();updateActions()}else boneLayerRedo()};
$('undo').onclick=()=>undo();$('redo').onclick=()=>redo();
const boneLayerSelection=updateSelection;updateSelection=function(){boneLayerSelection();updateBoneUI()};
const boneLayerActions=updateActions;updateActions=function(message){boneLayerActions(message);updateBoneUI()};
const boneLayerLoad=load;load=async function(){boneState.rig=null;await boneLayerLoad();boneState.rig=model?.rig?cloneRig(model.rig):null;boneState.cache.clear();boneState.pose={};boneState.poseUndo=[];boneState.poseRedo=[];if(!boneState.rig)boneState.mode='layers';updateBoneUI();render()};
$('boneV2').onclick=async()=>{if(saving||readonly||history.length)return;saving=true;updateActions();status('저장한 본·메시·웨이트로 Unity V2를 만드는 중…');try{const endpoint=shareToken?`/share/rig/${encodeURIComponent(shareToken)}/rig-v2`:`/api/jobs/${encodeURIComponent(jobId)}/rig-v2`;const result=await api(endpoint,{revision:model.revision});await load();$('packageV2').href=result.packageV2;$('packageV2').hidden=false;status(`Unity V2 생성 완료 · 본 ${result.boneCount}개`)}catch(error){status(error.message,true)}finally{saving=false;updateActions()}};
updateBoneUI();
