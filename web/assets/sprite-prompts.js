/* Reference-aware motion drafting. Existing prompts change only on explicit apply. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 if(!$('spriteAnalyze'))return;
 let source='',revision=0,configured=false,profile=null,draft=null,applied=null,restored=null;
 let analyzing=false,planning=false,analysisRequest=null,planRequest=null,analysisRun=null;
 const watched=['action','duration','loop','facing','subjectType','motionStrength','blink','combatEffect','effectStrength','effectDescription'];
 const names={human:'인간형',creature:'생물 / 괴물',hover_machine:'부유 기계',ground_machine:'지상 기계',left:'왼쪽',right:'오른쪽',front:'정면',back:'후면',preserve:'원본 유지'};
 function settings(){return {description:$('spriteDescription').value,notes:$('spriteMotionNotes').value,
  animationType:$('action').value,duration:Number($('duration').value),loop:$('loop').checked,
  facing:$('facing').value,subjectType:$('subjectType').value,motionStrength:$('motionStrength').value,
  blinkMode:$('blink').value,combatEffect:$('combatEffect').value,effectStrength:$('effectStrength').value,
  effectDescription:$('effectDescription').value};}
 const signature=()=>JSON.stringify(settings());
 function controls(){
  $('spriteAnalyze').disabled=!configured||!source||analyzing;
  $('spritePlan').disabled=!configured||!source||!profile||analyzing||planning;
  $('spriteApplyPrompt').disabled=!draft||planning;
  $('spriteDescription').disabled=analyzing||planning;
  $('spriteUseSuggested').disabled=!profile||analyzing||planning;
  $('spriteAnalyze').textContent=analyzing?'캐릭터 특징 분석 중…':'캐릭터 특징 다시 분석하기';
  $('spritePlan').textContent=planning?'동작을 설계하고 있어요…':'선택한 동작 설명 만들기';
 }
 async function api(path,body,controller){
  let timedOut=false;const timer=setTimeout(()=>{timedOut=true;controller.abort();},75000);
  try{
   const response=await fetch('/api/sprite-prompts/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Sprite-Request':'1'},body:JSON.stringify(body),signal:controller.signal});
   const result=await response.json();if(!response.ok)throw Error(result.error||'AI 요청에 실패했습니다.');return result;
  }catch(error){if(timedOut)throw Error('AI 응답이 늦어지고 있습니다. 잠시 후 다시 눌러 주세요.');throw error;}
  finally{clearTimeout(timer);}
 }
 function invalidate(){
  planRequest?.abort();planning=false;draft=null;$('spriteDraft').hidden=true;
  if(profile)$('spritePlanStatus').textContent='현재 특징과 설정으로 동작 설명을 만들 수 있어요.';
  controls();
 }
 function setImage(data){
  if(data===source)return;
  analysisRequest?.abort();planRequest?.abort();revision++;source=data;profile=null;analyzing=planning=false;
  if(applied&&$('prompt').value===applied.prompt){$('prompt').value=selectedPreset();}
  applied=null;$('spriteProfile').hidden=true;$('spriteDescription').value='';invalidate();
  $('spriteAnalysisStatus').textContent=configured?'새 이미지입니다. 캐릭터 특징을 분석해 주세요.':'AI 연결 확인 후 분석할 수 있습니다.';
  $('spritePlanStatus').textContent='이미지의 특징을 먼저 분석해 주세요.';
  if(configured&&$('spriteAnalyzeAuto').checked)analyze();
 }
 function analyze(){
  if(!analyzing&&configured&&source)analysisRun=runAnalysis();
  return analysisRun;
 }
 async function runAnalysis(){
  const token=revision,original=source,controller=new AbortController();analysisRequest=controller;
  invalidate();analyzing=true;controls();$('spriteAnalysisStatus').textContent='얼굴·복장·무기와 잡고 있는 손을 확인하고 있어요…';
  try{
   const result=await api('analyze',{imageData:original},controller);
   if(token!==revision||analysisRequest!==controller)return;
   profile=result.profile;$('spriteDescription').value=profile.description;
   $('spriteUncertainty').textContent=profile.uncertainty?'확인 필요: '+profile.uncertainty:'';
   $('spriteSuggestedSettings').textContent=`분석한 유형: ${names[profile.subjectType]||profile.subjectType} · 방향: ${names[profile.facing]||profile.facing}`;
   $('spriteProfile').hidden=false;
   $('spriteAnalysisStatus').textContent=result.cached?'저장된 분석을 불러왔어요. 특징이 맞는지 확인하세요.':'분석 완료. 특징이 맞는지 확인하고 아래에서 동작 설명을 만드세요.';
   $('spritePlanStatus').textContent='원하는 동작을 고르고, 필요한 움직임을 덧붙여 주세요.';
  }catch(error){if(token===revision&&error.name!=='AbortError')$('spriteAnalysisStatus').textContent=error.message;}
  finally{if(token===revision&&analysisRequest===controller){analyzing=false;controls();}}
 }
 async function plan(){
  if(!profile||planning||analyzing)return;
  if($('spriteDescription').value.trim().length<20){$('spritePlanStatus').textContent='보존할 특징을 20자 이상 입력해 주세요.';return;}
  const token=revision,captured=signature(),controller=new AbortController();planRequest=controller;
  draft=null;$('spriteDraft').hidden=true;planning=true;controls();
  $('spritePlanStatus').textContent='선택한 동작의 준비·실행·반동·복귀를 설계하고 있어요…';
  try{
   const result=await api('plan',settings(),controller);
   if(token!==revision||planRequest!==controller||captured!==signature())return;
   draft={...result,signature:captured,revision:token};
   $('spritePlanSummary').textContent=result.summary;$('spriteDraftPrompt').value=result.prompt;
   $('spriteDraft').hidden=false;$('spritePlanStatus').textContent='동작 초안이 준비됐어요. 내용을 확인하고 적용해 주세요.';
  }catch(error){if(token===revision&&planRequest===controller&&error.name!=='AbortError')$('spritePlanStatus').textContent=error.message;}
  finally{if(token===revision&&planRequest===controller){planning=false;controls();}}
 }
 $('spriteAnalyze').onclick=analyze;$('spritePlan').onclick=plan;
 $('spriteAnalyzeAuto').onchange=()=>{if($('spriteAnalyzeAuto').checked&&source&&!profile)analyze();};
 $('spriteUseSuggested').onclick=()=>{
  if(!profile)return;
  $('subjectType').value=profile.subjectType;currentSubject=profile.subjectType;
  $('blink').disabled=currentSubject.endsWith('machine');if($('blink').disabled)$('blink').value='none';
  $('facing').value=profile.facing;invalidate();
  $('spriteAnalysisStatus').textContent='분석한 대상 유형과 방향을 생성 설정에 반영했어요.';
 };
 function applyDraft(){
  if(!draft)return false;
  if(draft.revision!==revision||draft.signature!==signature()){invalidate();$('spritePlanStatus').textContent='이미지나 설정이 바뀌었어요. 현재 설정으로 다시 만들어 주세요.';return false;}
  const prompt=$('spriteDraftPrompt').value.trim();if(prompt.length<100||prompt.length>3800){$('spritePlanStatus').textContent='자세한 설명은 100~3800자로 입력해 주세요.';return false;}
  $('prompt').value=prompt;restored=null;applied={prompt,revision,signature:signature()};
  $('spritePlanStatus').textContent='생성에 적용했어요. 아래 만들기 버튼으로 시작하세요.';
  return true;
 }
 $('spriteApplyPrompt').onclick=applyDraft;
 const drafts=()=>configured&&!!source&&$('spriteAnalyzeAuto').checked;
 /* A hand-written or example prompt is the user's choice; only the default text or an out-of-date draft is replaced. */
 async function prepare(){
  if(!drafts())return '';
  const text=$('prompt').value,ownDraft=applied?.prompt===text;
  if(ownDraft&&applied.revision===revision&&applied.signature===signature())return '';
  if(!ownDraft&&text!==selectedPreset())return '';
  if(ownDraft){applied=null;$('prompt').value=selectedPreset();}
  $('message').textContent='AI가 내 캐릭터에 맞게 동작을 설계하고 있어요…';
  if(!profile)await analyze();
  if(profile){
   if(!draft||draft.revision!==revision||draft.signature!==signature())await plan();
   if(applyDraft())return '';
  }
  return 'AI 설계에 실패해 기본 동작으로 만듭니다';
 }
 for(const id of ['spriteDescription','spriteMotionNotes'])$(id).addEventListener('input',invalidate);
 document.addEventListener('change',event=>{if(watched.includes(event.target.id))invalidate();});
 $('effectDescription').addEventListener('input',invalidate);
 window.spritePromptAssistant={setImage,prepare,drafts,
  validate(){
   if(applied&&(applied.revision!==revision||applied.signature!==signature())&&$('prompt').value===applied.prompt){
    $('spritePlanStatus').textContent='AI 설명을 적용한 뒤 설정이 바뀌었어요. 현재 설정으로 설명을 다시 만들고 적용해 주세요.';
    $('message').textContent=$('spritePlanStatus').textContent;return false;
   }return true;
  },
  payload(){return {motionPromptMode:applied?.revision===revision&&applied?.signature===signature()||restored===$('prompt').value?'image-guided':'manual'};},
  restore(saved){applied=null;restored=saved.motionPromptMode==='image-guided'?saved.prompt:null;invalidate();}
 };
 fetch('/api/sprite-prompts/status').then(async response=>{const result=await response.json();if(!response.ok)throw Error(result.error||'AI 연결 확인 실패');configured=!!result.configured;
  $('spriteAutoBlock').hidden=!configured;
  $('spriteAnalysisStatus').textContent=configured?'이미지를 넣으면 캐릭터 특징을 분석합니다.':'AI 설계를 사용할 수 없어 기본 동작으로 만들어요.';
  controls();if(configured&&source&&$('spriteAnalyzeAuto').checked)analyze();
 }).catch(()=>{$('spriteAnalysisStatus').textContent='AI 연결을 확인하지 못했습니다. 새로고침 후 다시 시도해 주세요.';controls();});
 if(typeof imageData==='string'&&imageData)setImage(imageData);
 controls();
})();
