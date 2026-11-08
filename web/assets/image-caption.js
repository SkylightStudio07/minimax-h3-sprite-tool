/* Drafts are optional and editable; generation never triggers analysis. */
(()=>{
 const el=id=>document.getElementById(id);let ready=false,pending=false,serial=0;
 function refresh(){el('describeReference').disabled=!ready||!source||pending;el('describeReference').textContent=pending?'이미지 분석 중…':'이미지 분석 후 AI 프롬프트 자동 생성'}
 el('captionPrivacy').textContent='팀 서버의 이미지 분석 모델로 처리합니다. 외부 AI 서비스로 이미지를 보내지 않아요. 초안은 확인한 뒤 설명에 적용하세요.';
 (window.imageModelsRequest||api('api/images/models')).then(s=>{ready=Boolean(s.caption?.ready&&!s.caption?.external);el('captionStatus').textContent=ready?'로컬 분석 준비됨 · CPU 분석에는 시간이 걸릴 수 있어요.':'로컬 이미지 분석 모델 설치 중입니다. 완료 후 새로고침해 주세요.';refresh()}).catch(()=>{el('captionStatus').textContent='이미지 분석 준비 상태를 확인하지 못했어요.'});
 const clearDraft=()=>{serial++;el('captionReview').hidden=true;el('captionDraft').value='';el('captionSummary').textContent='';if(ready)el('captionStatus').textContent='머리·얼굴·의상·소품의 세부 특징을 분석해 프롬프트를 만들 수 있어요.';refresh()};window.addEventListener('image-reference-ready',clearDraft);window.addEventListener('image-reference-cleared',clearDraft);
 el('describeReference').onclick=async()=>{
  if(!ready||!source||pending)return;
  const version=serial,input=sourceData,started=Date.now();pending=true;refresh();el('captionTools').setAttribute('aria-busy','true');el('captionStatus').textContent='머리·얼굴·의상·소품을 자세히 분석하고 있어요. 기존 설명은 유지됩니다.';
  const timer=setInterval(()=>{if(version===serial)el('captionStatus').textContent=`외형 분석 중 · ${Math.floor((Date.now()-started)/1000)}초 경과. CPU로 처리하므로 잠시 걸릴 수 있어요. 기존 설명은 유지됩니다.`},1000);
  try{
   const result=await api('api/images/describe',{imageData:input});
   if(version!==serial||input!==sourceData)return;
   el('captionDraft').value=result.prompt;el('captionSummary').textContent=result.summary;el('captionReview').hidden=false;el('captionStatus').textContent=`상세 프롬프트 ${result.prompt.length.toLocaleString()}자 생성 · 내용을 확인하고 설명에 적용하세요.`;
  }catch(e){if(version===serial)el('captionStatus').textContent=e.message}
  finally{clearInterval(timer);el('captionTools').setAttribute('aria-busy','false');pending=false;refresh()}
 };
 function apply(replace){const text=el('captionDraft').value.trim();if(!text)return;const old=el('prompt').value.trim(),value=replace||!old?text:old+', '+text;if(value.length>el('prompt').maxLength){el('captionStatus').textContent='설명이 너무 길어요. 초안을 줄여 주세요.';return}el('prompt').value=value;el('prompt').dispatchEvent(new Event('input',{bubbles:true}));el('captionStatus').textContent='설명에 적용했어요. 원하는 변화도 덧붙인 뒤 생성하세요.';el('prompt').focus()}
 el('captionAppend').onclick=()=>apply(false);el('captionReplace').onclick=()=>apply(true);refresh();
})();
