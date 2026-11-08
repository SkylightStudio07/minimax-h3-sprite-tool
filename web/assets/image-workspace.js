/* User tasks coordinate the existing generation engine without exposing its vocabulary. */
(()=>{
 const el=id=>document.getElementById(id);
 let task='create',changing=false,initialized=false;
 let asset={type:'illustration',directionCount:1,facing:'front'};
 const copy={
  pixel:['도트로 만들 대상','외형과 색을 간단히 설명하세요. 전용 모델로 생성하고 최종 픽셀 크기와 색상 수를 맞춥니다.','도트 캐릭터·소품 설명','픽셀 아트 만들기','최종 PNG는 실제 도트 크기입니다. 확대 미리보기와 원본을 비교하고 Aseprite에서 다듬으세요.'],
  create:['만들 이미지 설명','외형과 의상을 설명하면 새 캐릭터 이미지를 만듭니다. 그림체는 예시를 보고 고를 수 있어요.','캐릭터 설명','이미지 만들기','생성한 후보를 비교하고 원하는 이미지를 골라 주세요.'],
  convert:['원화를 전투 스프라이트로','원화의 외형을 참고해 방향과 전투 자세를 바꿉니다.','남길 외형과 의상','스프라이트 후보 만들기','입력 이미지 → 방향·자세 조정 → 후보 비교 → 부분 수정'],
  edit:['바꿀 부분 설명','이미지를 올리고 바꿀 부분만 붉게 칠하세요. 칠하지 않은 영역은 유지됩니다.','어떻게 고칠까요?','칠한 부분 수정하기','B 칠하기 · E 지우기 · Ctrl+Z 되돌리기. 붉은 영역만 바뀝니다.'],
  sheet:['4방향 캐릭터 시트','캐릭터 외형을 설명하고 도트풍 또는 SD풍을 고르세요. 생성 후 방향과 정렬을 확인해 주세요.','캐릭터 설명','4방향 시트 만들기','3열 × 4행 시트 초안. 프레임 정렬·방향별 의상은 확인이 필요해요.']
 };
 const examples={knight:'adult knight, silver bob hair, blue eyes, navy long coat, leather gloves, black boots, travel bag',scout:'adult scout, short auburn hair, grey tactical jacket, black fitted trousers, combat boots, mechanical gauntlet',mage:'adult mage, long teal hair, cream cloak, dark green tunic, leather boots, wooden staff'};
 function canUse(id){return models.some(m=>m.id===id&&m.ready)}
 function selectModel(id){if(!canUse(id))throw Error('이 작업의 생성 도구가 준비되지 않았어요. 다른 작업을 선택하거나 잠시 후 다시 시도해 주세요.');el('model').value=id;el('model').dispatchEvent(new CustomEvent('change',{detail:{assetSetup:true}}))}
 function syncAsset(){asset.type=task==='pixel'?'side':task==='convert'?'side':task==='sheet'?'topdown':el('assetKind').value;asset.facing=asset.type==='live2d'?'front':el('assetFacing').value;if(task==='sheet'){asset.directionCount=4;asset.outputMode='four-direction-sheet'}else{if(![1,4,8].includes(asset.directionCount))asset.directionCount=1;delete asset.outputMode}}
 function refresh(){
  const setupNames={'soya-anima-flanime':'기본 일러스트 · 추천','wai-cutscene-counter':'셀 채색 · 전투 캐릭터','anima-base':'담백한 애니메이션','anima-turbo':'빠른 시안','animagine-xl':'선명한 애니메이션','illustrious-xl':'섬세한 일러스트','flanime-xl':'선명한 게임 일러스트'};
  for(const option of el('model').options){const m=models.find(m=>m.id===option.value);option.textContent=(setupNames[option.value]||m?.name||option.textContent)+(m&&!m.ready?' · 준비 중':'');option.disabled=Boolean(m&&(!m.ready||m.modes&&!m.modes.includes(el('mode').value)))}
  el('generationSetup').hidden=task==='sheet'||task==='pixel';el('referencePromptGuide').hidden=task!=='convert';el('referenceSetup').hidden=!['edit','convert'].includes(task)&&!(task==='pixel'&&el('mode').value==='reference');el('jumpToReference').disabled=!source;el('jumpToReference').textContent=task==='edit'?'수정 영역 칠하러 가기':'원본 크게 확인하기';el('referenceTitle').textContent=task==='edit'?'바꿀 부분만 칠하기':'입력 이미지 확인';el('changeAmountValue').textContent=Math.round(Number(el('denoise').value)*100)+'%';
  el('pixelControls').hidden=el('model').value!=='pixel-art-xl';el('libraryToggle').hidden=el('model').value==='pixel-art-xl';
  const c=copy[task];el('taskTitle').textContent=c[0];el('taskHelp').textContent=c[1];el('promptLabel').textContent=c[2];el('generate').textContent=busy?'작업 처리 중…':c[3];el('workspaceHint').textContent=c[4];
  document.querySelectorAll('[data-task]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.task===task));b.disabled=busy||!models.length});
  el('assetBasics').hidden=task!=='create';el('sheetControls').hidden=task!=='sheet';el('facingControls').hidden=task!=='convert'&&!(task==='create'&&!['illustration','live2d'].includes(asset.type));el('changeAmount').hidden=!['edit','convert'].includes(task)&&!(task==='pixel'&&el('mode').value==='reference');el('editPose').disabled=el('poseEnabled').disabled;
  el('promptExamples').hidden=task!=='create'&&task!=='sheet';el('promptHelp').textContent=task==='edit'?'예: black coat, clean silhouette, grey background. 붉게 칠한 부분에 새로 그릴 내용을 적으세요.':task==='convert'?'이미지는 외형의 기준이고, 설명은 무엇을 남기고 어떻게 바꿀지 알려주는 역할이에요. 영어 단어나 문장을 권장해요.':'머리·의상·소품을 영어 단어나 문장으로 적으면 더 잘 반영돼요.';
  const labels={'soya-anima-flanime':'기본 일러스트','wai-cutscene-counter':'셀 채색 전투','anima-base':'담백한 애니메이션','flanime-xl':'선명한 게임 일러스트','anima-turbo':'빠른 시안','animagine-xl':'선명한 애니메이션','illustrious-xl':'섬세한 일러스트'};
  const active=el('lookActive').textContent;el('selectedLook').textContent=el('styleId')?.value?window.imageStyleName(el('styleId').value):active.startsWith('적용 중:')?active.split(' · ')[0].replace('적용 중: ',''):labels[el('model').value]||'직접 선택한 그림체';el('selectedLookNote').textContent='기본: '+(setupNames[el('model').value]||'직접 선택')+' · 추가: '+(el('styleId')?.value?window.imageStyleName(el('styleId').value):'사용 안 함');el('activeGenerationSettings').textContent=el('selectedLookNote').textContent;el('model').disabled=busy;if(el('styleId'))el('styleId').disabled=busy;el('styleSettingControls').inert=busy;el('imageLibraryWide').inert=busy;el('libraryToggle').disabled=busy;
  const [w,h]=el('size').value.split('x').map(Number),model=models.find(m=>m.id===el('model').value);const factor=model?.id==='pixel-art-xl'?Number(el('pixelSize').value)/w:model?.id==='soya-anima-flanime'?2:el('hiresFix').checked?2:1;
  el('seed').max=(model?.maxSeed??9007199254740987)-Number(el('count').value)+1;
  el('size').disabled=model?.id==='pixel-art-xl';
  el('generationSummary').textContent=`${el('count').value}장 · ${w*factor} × ${h*factor} · ${el('mode').value==='inpaint'?'기존 배경 유지':el('background').value==='transparent'?'투명 PNG':'배경 유지'}`;
  el('outputSizeNote').textContent=model?.id==='pixel-art-xl'?'전용 생성 해상도에서 최근접 축소해 실제 도트 크기로 저장합니다.':factor===2?`선택한 크기의 2배인 ${w*2} × ${h*2}로 저장됩니다.`:'선택한 크기로 저장됩니다.';
  if(!models.length){el('selectedLook').textContent='그림체를 불러오는 중…';el('selectedLookNote').textContent='사용할 수 있는 그림체와 준비 상태를 확인하고 있어요.';el('activeGenerationSettings').textContent=el('selectedLookNote').textContent}
  el('resultEmpty').hidden=el('results').children.length>0;el('resultNextStep').hidden=!el('results').children.length;
  el('background').disabled=el('mode').value==='inpaint';
  window.refreshImageModelGallery?.();
 }
 function setTask(next,{preserve=false}={}){
  if(busy){status('현재 작업이 끝난 뒤 작업 방식을 바꿔 주세요.');return false}
  if(!copy[next])return false;
  changing=true;
  try{
   if(!preserve){
    if(next==='pixel'){
     window.applyPixelRecipe();
    }else if(next==='create'){
     window.restoreImageLook?.({});window.restoreImageStyle?.({});window.restoreImagePose?.({});el('mode').value='text';selectModel('soya-anima-flanime');el('preset').value=el('assetKind').value==='live2d'?'live2d':'illustration';el('count').value='1';
    }else if(next==='convert'){
     if(!canUse('wai-cutscene-counter'))throw Error('전투 스프라이트 도구를 준비 중이에요. 잠시 후 다시 시도해 주세요.');window.applyCutsceneRecipe();el('faceDetail').checked=false;el('mode').value='reference';modeChanged();el('denoise').value=.8;el('count').value='3';el('assetKind').value='side';el('assetFacing').value='right';window.applyReferenceBattlePose?.();
    }else if(next==='edit'){
     window.restoreImageLook?.({});window.restoreImagePose?.({});el('faceDetail').checked=false;el('hiresFix').checked=false;
     if(!['wai-cutscene-counter','anima-turbo','animagine-xl','illustrious-xl'].includes(el('model').value)){selectModel('wai-cutscene-counter');window.restoreImageStyle?.({})}
     el('mode').value='inpaint';modeChanged();el('denoise').value=.3;el('count').value='1';el('preset').value='illustration';
    }else if(next==='sheet')window.applyRpgSheet(el('sheetStyle').value==='sd'?'rpgchara-illustrious':'rpgchara-anima');
   }
   task=next;if(next!=='sheet')asset.directionCount=1;syncAsset();modeChanged();refresh();window.closeImageLibrary?.();status(next==='pixel'?'픽셀 전용 세팅입니다. 준비 상태와 도트 크기를 확인한 뒤 생성하세요.':next==='convert'?'전투 변환을 준비했어요. 입력 이미지를 올리고 남길 특징을 설명하세요.':next==='edit'?'입력 이미지를 올리거나 생성 결과에서 부분 수정을 선택하세요.':next==='sheet'?'캐릭터를 설명하고 시트 만들기를 눌러 주세요.':'캐릭터를 설명하고 이미지 만들기를 눌러 주세요.');return true;
  }catch(e){status(e.message);return false}finally{changing=false}
 }
 window.assetStart={payload:()=>task==='pixel'?{}:({assetSpec:{...asset}}),restore:s=>{if(s?.type){asset={...s};el('assetKind').value=s.type;el('assetFacing').value=s.facing||'front';if(!changing)refresh()}},plan:s=>{if(s?.type){asset={...s};el('assetKind').value=s.type;el('assetFacing').value=s.facing||'front';refresh()}},open:()=>el('assetKind').focus()};
 document.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>setTask(b.dataset.task));
 window.imageLookAllowed=look=>{const mode=el('mode').value;if(el('model').value==='pixel-art-xl')return false;if(mode==='text'&&!el('poseEnabled').checked)return true;if(look.sheetPreset)return false;const m=models.find(m=>m.id===look.model);return (m?.modes||['text','reference','inpaint']).includes(mode)&&(!el('poseEnabled').checked||(window.imagePoseState?.models||[]).includes(look.model))};
 el('jumpToReference').onclick=()=>el('referencePanel').scrollIntoView({behavior:'smooth',block:'start'});
 el('browseStyles').onclick=()=>window.openImageLibrary('styleGallery');el('chooseLook').onclick=()=>window.openImageLibrary('lookGallery');el('editPose').onclick=()=>window.openImageLibrary('posePanel');
 el('sheetStyle').onchange=()=>setTask('sheet');
 el('assetKind').onchange=()=>{if(el('assetKind').value==='side'){changing=true;window.applyCutsceneRecipe();changing=false;asset.type='side';el('assetFacing').value='right'}else if(el('assetKind').value==='live2d'){el('preset').value='live2d';el('assetFacing').value='front'}else el('preset').value=el('assetKind').value==='illustration'?'illustration':'sprite';syncAsset();refresh()};
 el('assetFacing').onchange=()=>{syncAsset();if(el('poseEnabled').checked){if(['left','right'].includes(asset.facing)){window.applyReferenceBattlePose?.();if(asset.facing==='left')el('poseMirror').click()}else window.restoreImagePose?.({})}refresh()};
 document.querySelectorAll('[data-example]').forEach(b=>b.onclick=()=>{el('prompt').value=examples[b.dataset.example];el('prompt').focus()});
 window.addEventListener('image-reference-ready',()=>{el('sourceFileNote').textContent=`${source.width} × ${source.height} · 이미지를 불러왔어요.`;el('canvasWrap').hidden=false;refresh()});
 const receive=window.receiveGeneratedImage;window.receiveGeneratedImage=async(file,s)=>{const result=await receive(file);if(s)window.assetStart.restore(s);return result};
 document.getElementById('imageLibraryWide').addEventListener('click',e=>{const b=e.target.closest('[data-use-look],[data-use-style]');if(!b||b.disabled)return;refresh();window.closeImageLibrary?.()});
 window.addEventListener('image-library-open',e=>{if(e.detail==='lookGallery'){if(task!=='create')el('lookGroup').value='';el('lookGroup').dispatchEvent(new Event('change'))}});
 const originalMode=modeChanged;modeChanged=function(){originalMode();if(!changing){task=el('model').value==='pixel-art-xl'?'pixel':el('preset').value==='rpg-sheet'?'sheet':el('mode').value==='reference'?'convert':el('mode').value==='inpaint'?'edit':'create';refresh()}};
 el('mode').onchange=()=>modeChanged();
 const originalModel=modelChanged;modelChanged=function(...args){originalModel(...args);if(!changing){if(el('model').value==='pixel-art-xl')task='pixel';else if(task==='pixel')task='create';refresh()}};
 const recreate=window.applyRecreatePreset;window.applyRecreatePreset=s=>{
  changing=true;
  try{
   const note=recreate(s),mode=['reference','inpaint'].includes(s.mode)?s.mode:'text';
   el('mode').value=mode;modeChanged();
   if(mode!=='text'){source=null;sourceData='';window.dispatchEvent(new Event('image-reference-cleared'));mc.clearRect(0,0,mask.width,mask.height);undo=[];el('file').value='';el('canvasWrap').hidden=true;el('sourceFileNote').textContent='이전 설정을 불러왔어요. 입력 이미지는 다시 선택해 주세요.';paint()}
   if(mode==='inpaint')window.restoreImagePose?.({});
   window.assetStart.restore(s.assetSpec||{type:s.preset==='rpg-sheet'?'topdown':s.preset==='live2d'?'live2d':'illustration',facing:'front',directionCount:s.preset==='rpg-sheet'?4:1});
   task=s.model==='pixel-art-xl'?'pixel':s.preset==='rpg-sheet'?'sheet':mode==='reference'?'convert':mode==='inpaint'?'edit':'create';
   if(s.preset==='rpg-sheet')el('sheetStyle').value=s.model==='anima-base'?'pixel':'sd';refresh();return note;
  }finally{changing=false}
 };
 const originalResults=showResults;showResults=function(job){originalResults(job);refresh();window.closeImageLibrary?.();document.querySelectorAll('#results img').forEach((img,i)=>{img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label',`후보 ${i+1} 크게 보기`);const open=()=>{viewerImg.src=img.src;viewer.showModal()};img.onclick=open;img.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}}});};
 const viewer=document.createElement('dialog');viewer.className='image-viewer';viewer.setAttribute('aria-label','생성 이미지 크게 보기');const close=document.createElement('button');close.type='button';close.className='ui-btn';close.textContent='닫기';close.onclick=()=>viewer.close();const viewerImg=document.createElement('img');viewerImg.alt='선택한 후보 이미지';viewer.append(close,viewerImg);document.body.append(viewer);
 new MutationObserver(refresh).observe(el('lookActive'),{childList:true,subtree:true});
 el('form').addEventListener('change',refresh);el('form').addEventListener('input',e=>{if(e.target.id!=='prompt'&&e.target.id!=='negativePrompt')refresh()});
 el('form').addEventListener('submit',e=>{syncAsset();if(el('mode').value!=='text'&&!source){e.preventDefault();e.stopImmediatePropagation();status('입력 이미지를 먼저 선택해 주세요.');el('file').focus();el('referenceSetup').scrollIntoView({behavior:'smooth'});return}if(el('mode').value==='inpaint'&&!mc.getImageData(0,0,mask.width,mask.height).data.some((v,i)=>i%4===3&&v>0)){e.preventDefault();e.stopImmediatePropagation();status('바꿀 부분을 붉게 칠해 주세요.');el('referencePanel').scrollIntoView({behavior:'smooth'});return}window.closeImageLibrary?.()},true);
 function ready(){if(initialized)return;initialized=true;try{const planned=JSON.parse(sessionStorage.getItem('sprite-asset-entry')||'null');if(planned){window.assetStart.plan(planned);sessionStorage.removeItem('sprite-asset-entry')}}catch{}refresh()}
 window.addEventListener('image-models-ready',ready);window.addEventListener('image-styles-ready',refresh);window.addEventListener('image-style-changed',refresh);if(models.length)ready();el('canvasWrap').hidden=!source;refresh();
})();
