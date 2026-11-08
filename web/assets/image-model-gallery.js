/* Visual choices delegate to the existing model/style controls and payloads. */
(()=>{
 const $=id=>document.getElementById(id);
 if(!$('baseModelCards'))return;
 let examples=[],failed=false;
 const safeText=(node,text)=>{if(node.textContent!==text)node.textContent=text};
 function availability(item){
  const model=models.find(m=>m.id===item.id),option=[...$('model').options].find(o=>o.value===item.id);
  if(!model||!model.ready)return '준비 중이에요';
  if($('preset').value==='rpg-sheet')return '4방향 시트 작업의 전용 그림체를 사용해요';
  if(model.modes&&!model.modes.includes($('mode').value))return $('mode').value==='inpaint'?'부분 수정을 지원하지 않아요':'원화 변형을 지원하지 않아요';
  if($('poseEnabled').checked&&!(window.imagePoseState?.models||[]).includes(item.id))return '현재 자세 고정과 함께 쓸 수 없어요';
  if(option?.disabled)return '현재 작업에서 사용할 수 없어요';
  return '';
 }
 function setImage(img,src,pixel=false){
  img.hidden=!src;
  if(src){if(img.getAttribute('src')!==src)img.src=src}else img.removeAttribute('src');
  img.classList.toggle('model-preview--pixel',pixel);
 }
 function choose(item){
  if(busy||availability(item))return;
  const previousStyle=$('styleId')?.value;
  if(item.id!==$('model').value){
   window.restoreImageLook?.({});
   if(item.pixel){
    $('pixelInput').value=$('mode').value==='reference'?'reference':'text';
    document.querySelector('[data-task="pixel"]').click();
   }else{
    $('model').value=item.id;
    $('model').dispatchEvent(new CustomEvent('change',{detail:{assetSetup:true}}));
   }
  }
  refresh();
  safeText($('styleSelectionStatus'),item.title+'을 선택했어요. '+(previousStyle&&!$('styleId')?.value?'함께 쓸 수 없는 추가 그림체는 해제했어요.':'내 캐릭터 설명을 입력해 생성하세요.'));
  window.closeImageLibrary?.();
 }
 function render(){
  $('baseModelCards').replaceChildren();
  for(const item of examples){
   const card=document.createElement('article');card.className='base-model-card';card.dataset.modelExample=item.id;
   const imageLink=document.createElement('a');imageLink.className='model-example-image';imageLink.href=item.preview;imageLink.target='_blank';imageLink.rel='noopener';imageLink.setAttribute('aria-label',item.title+' 생성 예시 크게 보기');
   const image=document.createElement('img');image.src=item.preview;image.alt=item.title+'로 생성한 오리지널 인물';image.loading='lazy';image.decoding='async';if(item.pixel)image.className='model-preview--pixel';imageLink.append(image);
   if(item.badge){const badge=document.createElement('span');badge.className='model-example-badge';badge.textContent=item.badge;imageLink.append(badge)}
   const content=document.createElement('div');content.className='model-example-copy';const name=document.createElement('h4');name.textContent=item.title;const note=document.createElement('p');note.textContent=item.description;
   const state=document.createElement('p');state.className='model-example-state';state.dataset.modelState=item.id;
   const apply=document.createElement('button');apply.type='button';apply.className='ui-btn';apply.dataset.useModel=item.id;apply.onclick=()=>choose(item);
   content.append(name,note,state,apply);card.append(imageLink,content);$('baseModelCards').append(card);
  }
  refresh();
 }
 function refresh(){
  const current=examples.find(x=>x.id===$('model').value);
  const fallback=$('model').selectedOptions[0]?.textContent||'그림체를 불러오는 중…';
  safeText($('modelChoiceName'),current?.title||fallback);
  safeText($('modelChoiceNote'),current?.description||(failed?'예시를 다시 불러와 주세요.':'생성 예시를 확인하고 있어요.'));
  setImage($('modelChoiceImage'),current?.preview,current?.pixel);
  $('chooseModel').disabled=busy||!models.length;
  for(const item of examples){
   const card=[...$('baseModelCards').children].find(c=>c.dataset.modelExample===item.id),button=card.querySelector('[data-use-model]');
   const reason=availability(item),selected=item.id===$('model').value;
   card.dataset.selected=String(selected);button.disabled=busy||Boolean(reason);button.setAttribute('aria-pressed',String(selected));
   safeText(button,selected?'선택한 그림체':reason?'사용할 수 없어요':'이 그림체 선택');
   safeText(card.querySelector('[data-model-state]'),reason||(selected?'현재 사용 중':item.pixel?'선택하면 픽셀 아트 작업으로 이동해요':'같은 설명으로 새로 생성한 예시'));
  }
  const style=window.imageStylePreview?.();
  safeText($('styleChoiceName'),style?.name||'추가하지 않음');
  safeText($('styleChoiceNote'),style?'선·채색을 기본 그림체에 더해요.':'원하는 선과 채색을 더해 보세요.');
  setImage($('styleChoiceImage'),style?.preview);
  $('styleChoiceEmpty').hidden=Boolean(style?.preview);
  $('clearExtraStyle').hidden=!$('styleId')?.value;$('clearExtraStyle').disabled=busy;
  $('browseStyles').disabled=busy;
 }
 $('chooseModel').onclick=()=>window.openImageLibrary?.('baseGallery');
 $('clearExtraStyle').onclick=()=>{if(busy)return;$('styleId').value='';$('styleId').dispatchEvent(new Event('change'));refresh()};
 window.refreshImageModelGallery=refresh;
 for(const name of ['image-models-ready','image-styles-ready','image-style-changed'])window.addEventListener(name,refresh);
 $('model').addEventListener('change',refresh);$('mode').addEventListener('change',refresh);$('poseEnabled').addEventListener('change',refresh);
 new MutationObserver(refresh).observe($('model'),{childList:true,attributes:true,attributeFilter:['disabled']});
 fetch(new URL('assets/image-model-examples/catalog.json',location.href)).then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{
  examples=data.examples;safeText($('baseModelLoading'),'');$('baseModelLoading').hidden=true;render();
 }).catch(()=>{failed=true;safeText($('baseModelLoading'),'그림체 예시를 불러오지 못했어요. 새로고침해 주세요.');refresh()});
 refresh();
})();
