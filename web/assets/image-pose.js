/* COCO-18 joint editor. Only normalized coordinates are submitted, never a graph. */
(()=>{
 const el=id=>document.getElementById(id),canvas=el('poseCanvas'),c=canvas.getContext('2d');
 const labels=['코','목','오른쪽 어깨','오른쪽 팔꿈치','오른쪽 손목','왼쪽 어깨','왼쪽 팔꿈치','왼쪽 손목','오른쪽 골반','오른쪽 무릎','오른쪽 발목','왼쪽 골반','왼쪽 무릎','왼쪽 발목','오른쪽 눈','왼쪽 눈','오른쪽 귀','왼쪽 귀'];
 const links=[[1,2],[1,5],[2,3],[3,4],[5,6],[6,7],[1,8],[8,9],[9,10],[1,11],[11,12],[12,13],[1,0],[0,14],[14,16],[0,15],[15,17]];
 const colors=['#f00','#f50','#fa0','#ff0','#af0','#5f0','#0f0','#0f5','#0fa','#0ff','#0af','#05f','#00f','#50f','#a0f','#f0f','#f0a','#f05'];
 const battle=[[575,245],[515,360],[480,385],[505,540],[650,555],[550,385],[610,460],[725,435],[480,790],[440,1070],[390,1400],[555,790],[625,1060],[705,1400],[583,229],[568,230],[560,242],[545,245]].map(([x,y])=>[x/1024,y/1536]);
 const referenceBattle=[[590,245],[520,355],[490,380],[555,520],[715,490],[555,375],[650,425],[750,365],[480,790],[420,1070],[365,1400],[555,790],[635,1060],[725,1400],[596,230],[583,231],[568,240],[557,244]].map(([x,y])=>[x/1024,y/1536]);
 const neutral=[[.5,.14],[.5,.24],[.4,.26],[.34,.43],[.31,.59],[.6,.26],[.66,.43],[.69,.59],[.44,.54],[.42,.73],[.4,.93],[.56,.54],[.58,.73],[.6,.93],[.48,.13],[.52,.13],[.455,.145],[.545,.145]];
 let points=structuredClone(battle),selected=-1,drag=null,history=[],reference=null,referenceSource=null,referenceSize='';
 labels.forEach((name,i)=>el('poseJoint').add(new Option(name,String(i))));el('poseJoint').onchange=()=>{selected=Number(el('poseJoint').value);draw();canvas.focus({preventScroll:true})};
 const copy=()=>points.map(p=>p.slice());
 function remember(){history.push(copy());if(history.length>60)history.shift()}
 function undoPose(){if(history.length)points=history.pop();draw()}
 function draw(){
  const [w,h]=el('size').value.split('x').map(Number);canvas.width=512;canvas.height=Math.round(512*h/w);c.fillStyle='#111';c.fillRect(0,0,canvas.width,canvas.height);
  if(reference&&el('poseReference').checked&&el('mode').value==='reference'){c.globalAlpha=.4;c.drawImage(reference,0,0,canvas.width,canvas.height);c.globalAlpha=1}
  c.lineWidth=4;c.lineCap='round';links.forEach(([a,b],i)=>{c.strokeStyle=colors[i];c.beginPath();c.moveTo(points[a][0]*canvas.width,points[a][1]*canvas.height);c.lineTo(points[b][0]*canvas.width,points[b][1]*canvas.height);c.stroke()});
  points.forEach(([x,y],i)=>{c.fillStyle=colors[i];c.beginPath();c.arc(x*canvas.width,y*canvas.height,i===selected?8:5,0,Math.PI*2);c.fill();if(i===selected){c.strokeStyle='white';c.lineWidth=2;c.stroke()}});
  el('poseSelected').textContent=selected<0?'관절을 클릭하거나 드래그하세요. 방향키 이동 · Shift로 크게 이동 · Ctrl+Z 되돌리기':`${labels[selected]} · X ${Math.round(points[selected][0]*100)}% / Y ${Math.round(points[selected][1]*100)}% · 방향키 이동 / Ctrl+Z 되돌리기`;
  el('poseUndo').disabled=!history.length;
  el('poseJoint').value=String(selected);
 }
 function refresh(){const state=window.imagePoseState;const supported=Boolean(state?.ready&&state.models.includes(el('model').value)&&el('mode').value!=='inpaint'&&el('preset').value!=='rpg-sheet');el('poseEnabled').disabled=!supported;if(!supported)el('poseEnabled').checked=false;el('poseAvailability').textContent=supported?'사용 가능 · 관절을 수정한 뒤 위 적용 옵션을 켜세요. 포즈는 생성 설정에도 저장됩니다.':'편집은 가능하며, 생성에 적용하려면 Flanime·셀 채색 혼합 모델과 설치된 전용 포즈 모델이 필요합니다.';updateFaceDetail();updateHiresFix();prepareReference();draw()}
 function position(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]}
 const clamp=v=>Math.max(0,Math.min(1,v));
 canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;const p=position(e),r=canvas.getBoundingClientRect();let best=Infinity;selected=-1;points.forEach(([x,y],i)=>{const d=Math.hypot((x-p[0])*r.width,(y-p[1])*r.height);if(d<best&&d<20){selected=i;best=d}});canvas.focus({preventScroll:true});if(selected>=0){e.preventDefault();remember();drag=e.pointerId;canvas.setPointerCapture(e.pointerId)}draw()});
 canvas.addEventListener('pointermove',e=>{if(drag!==e.pointerId)return;points[selected]=position(e).map(clamp);draw()});
 function end(e){if(drag===e.pointerId){drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId)}}
 canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);canvas.addEventListener('lostpointercapture',()=>{drag=null});
 canvas.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.stopPropagation();undoPose();return}const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!delta||selected<0)return;e.preventDefault();remember();points[selected]=points[selected].map((v,i)=>clamp(v+delta[i]*(e.shiftKey ? 0.02 : 0.003)));draw()});
 el('poseUndo').onclick=undoPose;el('poseReset').onclick=()=>{remember();points=structuredClone(el('posePreset').value==='neutral'?neutral:battle);selected=-1;draw()};el('posePreset').onchange=()=>el('poseReset').click();
 el('poseMirror').onclick=()=>{remember();points=points.map(([x,y])=>[1-x,y]);for(const [a,b] of [[2,5],[3,6],[4,7],[8,11],[9,12],[10,13],[14,15],[16,17]])[points[a],points[b]]=[points[b],points[a]];draw()};
 el('poseEnabled').onchange=refresh;el('poseReference').onchange=draw;el('size').addEventListener('change',()=>{prepareReference();draw()});el('model').addEventListener('change',refresh);el('mode').addEventListener('change',refresh);window.addEventListener('image-models-ready',refresh);window.addEventListener('image-sheet-ready',refresh);el('preset').addEventListener('change',refresh);
 function prepareReference(){if(referenceSource===source&&referenceSize===el('size').value)return;referenceSource=source;referenceSize=el('size').value;reference=null;if(!source)return;const tmp=document.createElement('canvas');tmp.width=source.width;tmp.height=source.height;const t=tmp.getContext('2d');t.drawImage(source,0,0);const data=t.getImageData(0,0,tmp.width,tmp.height).data;let x0=tmp.width,y0=tmp.height,x1=-1,y1=-1;for(let y=0;y<tmp.height;y++)for(let x=0;x<tmp.width;x++)if(data[(y*tmp.width+x)*4+3]){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y)}if(x1<0)return;const [w,h]=el('size').value.split('x').map(Number);reference=document.createElement('canvas');reference.width=w;reference.height=h;const rc=reference.getContext('2d');rc.fillStyle='rgb(210,210,210)';rc.fillRect(0,0,w,h);const scale=Math.min(w*960/1024/(x1-x0+1),h*1472/1536/(y1-y0+1)),dw=(x1-x0+1)*scale,dh=(y1-y0+1)*scale;rc.drawImage(source,x0,y0,x1-x0+1,y1-y0+1,(w-dw)/2,(h-dh)/2,dw,dh)}
 window.addEventListener('image-reference-ready',()=>{prepareReference();draw()});
 window.applyReferenceBattlePose=()=>{remember();points=structuredClone(referenceBattle);selected=-1;el('poseStrength').value=1.2;el('poseEnabled').checked=true;refresh();draw()};
 window.imagePosePayload=()=>el('poseEnabled').checked&&!el('poseEnabled').disabled?{pose:{points:copy(),strength:Number(el('poseStrength').value)}}:{};
 window.restoreImagePose=settings=>{if(settings.pose?.points?.length===18){points=structuredClone(settings.pose.points);el('poseStrength').value=settings.pose.strength;history=[];selected=-1;el('poseEnabled').checked=true}else el('poseEnabled').checked=false;refresh()};
 el('counterConvert').onclick=()=>{if(!models.some(m=>m.id==='flanime-xl'&&m.ready)||!window.imageStyleAvailable?.('counter-side-sprites','illustrious')){status('전투 형식 모델을 불러오는 중입니다. 잠시 뒤 다시 눌러 주세요.');return}window.assetStart?.restore({type:'side',directionCount:1,facing:'right'});el('poseEnabled').checked=false;window.restoreImageLook?.({});el('model').value='flanime-xl';el('model').dispatchEvent(new Event('change'));el('mode').value='reference';el('mode').dispatchEvent(new Event('change'));window.restoreImageStyle?.({styleId:'counter-side-sprites',styleStrength:.6});el('steps').value=32;el('cfg').value=5;el('size').value='1024x1536';el('size').dispatchEvent(new Event('change'));el('denoise').value=.3;el('referencePanel').scrollIntoView({behavior:'smooth'});window.openImageLibrary?.('posePanel');status('전투 형식 원화 변형을 준비했어요. 참고 이미지를 올리고 캐릭터 설명을 입력하세요.')};
 refresh();
})();
