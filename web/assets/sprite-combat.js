/* Joint AI effects and the reviewed pixel export, using the existing job flow. */
(()=>{
 'use strict';
 const el=id=>document.getElementById(id);
 const defaultHint=el('combatEffectHint').textContent;
 window.spriteCombatPayload=()=>({combatEffect:el('combatEffect').value,effectStrength:el('effectStrength').value,effectDescription:el('effectDescription').value,pixelOutput:el('pixelOutput').checked,pixelColorLock:el('pixelColorLock').checked});
 window.spriteCombatControls=()=>{
  const effect=el('combatEffect').value!=='none',pixel=el('pixelOutput').checked;
  const subtle=el('combatEffect').value==='subtle';
  el('combatEffectHint').textContent=subtle?'칼날 가까이에 짧고 옅은 빛을 더합니다. 전신과 검이 모두 보이는 이미지로 시작하세요. 강도는 빛의 밝기를 조절하며 크기를 정확한 비율로 고정하지는 않습니다.':defaultHint;
  el('effectDescription').placeholder=subtle?'예: 칼날에 옅은 푸른 빛, 베는 순간에만 짧게':'예: 검을 내리칠 때 푸른 초승달 검기, 끝에서 금빛 불꽃이 짧게 흩어지게';
  el('combatEffectFields').hidden=!effect;el('pixelExportFields').hidden=!pixel;
  el('effectDescription').required=el('combatEffect').value==='custom';
  el('effectDescription').setAttribute('aria-required',String(el('effectDescription').required));
  el('effectDescription').previousElementSibling.textContent=el('effectDescription').required?'이펙트 설명 · 필수':'이펙트 추가 설명 · 선택';
  if(effect||pixel){
   el('backgroundRemoval').value='flat';
   for(const option of el('backgroundRemoval').querySelectorAll('[value^="ai"],[value="green"]'))option.disabled=true;
   el('flatBackgroundControls').hidden=!el('removeBackground').checked;
   el('spriteBackgroundNote').textContent=subtle&&!pixel?'입력 배경을 먼저 정리하고, 캐릭터의 옷과 옅은 검기를 함께 보호합니다. 원본 영상과 시트도 보관합니다.':'단색 배경을 제거해 검기·불꽃도 함께 남깁니다. 복잡한 배경의 입력은 먼저 배경을 제거해 주세요. 작은 틈이나 옅은 효과는 직접 확인하세요.';
  }else{
   // Leaving a pixel/effect preset must release its temporary AI lock.
   // Engine availability is recorded by check(), separately from this lock.
   for(const option of el('backgroundRemoval').querySelectorAll('[value^="ai"],[value="green"]'))option.disabled=option.dataset?.ready==='false';
   el('spriteBackgroundNote').textContent=el('backgroundRemoval').value==='green'?'초록 배경 위에서 영상을 만든 뒤 초록만 지웁니다. 회색 몸체가 덜 비치고 폭발과 연기도 남습니다. 밝은 초록색이 많은 캐릭터에는 쓸 수 없고, 폭발 가장자리에 노란 초록빛이 조금 남을 수 있습니다.':el('backgroundRemoval').value==='ai-soft'?'AI로 캐릭터를 남기고, 단색 배경 위의 폭발과 연기는 가장자리가 부드럽게 남습니다. 배경이 단색이 아니면 일반 AI 제거로 처리됩니다.':el('backgroundRemoval').value==='ai-sparks'?'AI로 캐릭터를 남기고 단색 배경 위 작은 금빛 불꽃도 함께 보존합니다. 복잡한 배경이나 다른 색 효과는 결과를 확인하세요.':el('backgroundRemoval').value==='ai'?'AI가 프레임별 배경을 제거합니다. 원본 영상과 시트는 함께 보존합니다. 머리카락·반투명 소품은 결과를 확인하세요.':'가장자리에서 이어지는 단색 배경을 제거합니다. 원본 영상과 시트는 함께 보존합니다.';
  }
  if(pixel){const [w,h]=calculatedSize();el('pixelExportSize').textContent=`시트 한 칸 ${w/4}×${h/4}px · PNG와 인계용 GIF로 받기`}
 };
 let beforeLock=null;
 function changed(){
  const active=el('combatEffect').value!=='none'||el('pixelOutput').checked;
  if(active){
   beforeLock??={stabilize:el('stabilize').checked,optimizeLoop:el('optimizeLoop').checked,backgroundRemoval:el('backgroundRemoval').value};
   el('stabilize').checked=false;el('optimizeLoop').checked=false;
  }else{
   const previous=beforeLock||{stabilize:true,optimizeLoop:true,backgroundRemoval:'ai'};beforeLock=null;
   el('stabilize').checked=previous.stabilize;el('optimizeLoop').checked=previous.optimizeLoop;el('backgroundRemoval').value=previous.backgroundRemoval;
   check();
  }
  window.spriteCombatControls();
 }
 for(const id of ['combatEffect','pixelOutput'])el(id).addEventListener('change',changed);
 for(const id of ['size','workflowId','file'])el(id).addEventListener('change',()=>window.spriteCombatControls());
 // setImage also handles the normal upload/drop path. Its preview mutation updates the size hint.
 new MutationObserver(()=>window.spriteCombatControls()).observe(el('drop'),{childList:true});
 el('applyChibiCombat').onclick=()=>{
  el('workflowId').value='standard';el('samplingMode').value='quality';
  el('action').value='attack';el('facing').value='right';el('subjectType').value='human';currentSubject='human';
  el('blink').value='none';el('blink').disabled=false;el('duration').value='3';el('frames').value='30';
  el('size').value='768x640';el('motionPadding').value='30';el('motionStrength').value='normal';
  el('loop').checked=true;el('stabilize').checked=false;el('optimizeLoop').checked=false;
  el('motionSpeed').value='1';el('trimAction').checked=false;motionTimingControls();
  el('negativeEnabled').checked=false;el('removeBackground').checked=true;el('backgroundRemoval').value='flat';
  el('combatEffect').value='blue_slash';el('effectStrength').value='normal';el('effectDescription').value='';
  el('pixelOutput').checked=true;el('pixelColorLock').checked=true;
  window.assetStart?.restore({type:'side',facing:'right',directionCount:1});
  el('prompt').value='Perform exactly ONE clear sword attack toward SCREEN RIGHT, then recover. At 0.0-0.4 seconds brace the boots, bend the knees and draw the sword hand back and up beside the rear shoulder. At 0.4-0.95 seconds deliver ONE fast decisive diagonal downward cut through the empty space in front toward screen right. Move the arm, shoulders and hips with one grounded weight shift. At 0.95-1.35 seconds follow through low and forward, then brake. At 1.35-2.2 seconds recover the opening compact ready stance at the same screen location and hold until the end. Preserve the exact input character, face, proportions, clothes, pixel size and square pixel clusters. Keep one rigid sword attached to the same hand, unchanged in length. No duplicate weapon, second attack, walking, jumping, full body spin, camera motion or scenery. Keep the entire character, weapon and effects inside the empty canvas.';
  workflowControls();backgroundControls();updateButtonText();window.spriteCombatControls();
  el('message').textContent='도트 검 공격 설정 적용 · 오른쪽을 보는 전신 도트 이미지를 넣어 주세요. 공격 1회 후 원래 자세로 복귀하며, 영상과 시트에서 결과를 확인할 수 있어요.';
 };
 window.spriteCombatControls();
})();
