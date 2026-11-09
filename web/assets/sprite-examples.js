/* Sample browsing never replaces the input image or submits a generation job. */
(()=>{
 'use strict';
 const el=id=>document.getElementById(id),root=el('spriteExamples');if(!root)return;
 let examples=[],selected=null,filter='pixel',view='motion',applied='',assetType=null,playing=!matchMedia('(prefers-reduced-motion: reduce)').matches;
 const category=item=>item.category||(item.style==='pixel'?'pixel':'normal');
 const categoryNames={pixel:'도트',normal:'일반',chibi:'치비'};
 const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n};
 const url=(item,suffix)=>item[suffix];
 const cards=new Map();
 const gifLink=make('a','ui-btn ui-btn--sm','샘플 GIF 받기');gifLink.hidden=true;gifLink.download='';el('spriteExampleApply').after(gifLink);
 const guide=make('section','sx-type-guide'),guideImage=make('img'),guideTitle=make('h3'),guideText=make('p'),guideBadge=make('span','sx-eyebrow');
 guide.id='spriteTypeGuide';guideImage.alt='';guide.append(guideImage,guideBadge,guideTitle,guideText);root.querySelector('.sx-disclaimer').after(guide);
 const summary=make('div','sprite-choice-summary'),summaryImage=make('img'),summaryText=make('div'),summaryTitle=make('b','','동작을 보고 골라 보세요'),summaryNote=make('small','','오른쪽에서 움직이는 예시와 시트를 비교합니다.'),summaryButton=make('button','ui-btn ui-btn--sm','예시 보기');
 summaryImage.hidden=true;summaryText.append(summaryTitle,summaryNote);summaryButton.type='button';summaryButton.onclick=()=>window.spriteWorkspace?.show('examples',true);summary.append(summaryImage,summaryText,summaryButton);
 el('action').previousElementSibling.before(summary);
 const recommendation=el('applyChibiCombat').onclick;
 el('applyChibiCombat').onclick=()=>{filter='pixel';recommendation();applyFilter('pixel');summaryTitle.textContent='도트 검 공격 추천 설정';summaryNote.textContent='추천값 적용 · 실제 입력으로 생성해 확인하세요.';summaryImage.hidden=true;applied='';};
 function markApplied(id){
  const item=examples.find(x=>x.id===id);if(!item)return;
  applied=id;summaryImage.src=item.poster;summaryImage.alt=item.title+' 설정 예시';summaryImage.hidden=false;summaryImage.style.imageRendering=item.style==='pixel'?'pixelated':'auto';
  summaryTitle.textContent=item.title+' 적용됨';summaryNote.textContent='예시 설정 · 내 이미지로 생성하면 결과가 달라져요.';
 }
 function syncPlayback(){
  el('spriteExamplePlayback').textContent=playing?'예시 애니메이션 정지':'예시 애니메이션 재생';
  el('spriteExamplePlayback').setAttribute('aria-pressed',String(playing));
  for(const item of examples){const img=cards.get(item.id)?.querySelector('img');if(img)img.src=url(item,playing?'animation':'poster')}
  if(selected&&view==='motion')el('spriteExampleHero').src=url(selected,playing?'animation':'poster');
 }
 function renderSelection(item){
  if(assetType!=='side'||!item||category(item)!==filter)return;
  selected=item;el('spriteExampleDetail').hidden=false;el('spriteExampleTitle').textContent=item.title;el('spriteExampleDescription').textContent=item.description;
  gifLink.hidden=!item.gif;if(item.gif)gifLink.href=item.gif;else gifLink.removeAttribute('href');
  el('spriteExampleReference').src=item.source;el('spriteExampleReference').dataset.style=item.style;el('spriteExampleNote').textContent=item.note;
  el('spriteExampleTags').replaceChildren(...[categoryNames[category(item)],...(item.pixelGrid?[`${item.pixelGrid.width}×${item.pixelGrid.height}px`]:[]),item.effect==='none'?'동작 중심':'공격 + 이펙트',item.recipe.loop?'반복 재생':'한 번 재생'].map(text=>make('span','',text)));
  el('spriteExampleStatus').textContent=applied===item.id?'현재 왼쪽에 적용된 예시 설정입니다.':'';
  for(const [id,card] of cards){card.setAttribute('aria-pressed',String(id===item.id));card.querySelector('.sx-card-selected').hidden=id!==item.id}
  setView(view);
 }
 function setView(next){
  view=next;el('spriteExampleMotion').setAttribute('aria-pressed',String(view==='motion'));el('spriteExampleSheet').setAttribute('aria-pressed',String(view==='sheet'));
  if(!selected)return;const hero=el('spriteExampleHero');hero.src=url(selected,view==='sheet'?'sheet':playing?'animation':'poster');hero.dataset.style=selected.style;hero.dataset.view=view;hero.alt=selected.title+(view==='sheet'?' · 실제 시트 예시':' · 실제 동작 예시');
  el('spriteExampleViewLabel').textContent=view==='sheet'?'시트 예시 · 축소 보기':'동작 예시 · 샘플 캐릭터';
  fitPixels();
 }
 function fitPixels(){
  const hero=el('spriteExampleHero'),stage=hero.parentElement;
  hero.style.width='';hero.style.height='';
  if(!selected?.pixelGrid||view==='sheet'||!stage.clientWidth)return;
  const {width,height}=selected.pixelGrid;
  const scale=Math.max(1,Math.floor(Math.min((stage.clientWidth-24)/width,(stage.clientHeight-24)/height)));
  hero.style.width=width*scale+'px';hero.style.height=height*scale+'px';
 }
 new ResizeObserver(fitPixels).observe(el('spriteExampleHero').parentElement);
 function renderCards(){
  el('spriteExampleCards').replaceChildren();cards.clear();
  for(const item of examples){
   const card=make('button','sx-card'),stage=make('div','sx-card-stage sx-checker'),image=make('img'),body=make('span','sx-card-body'),badge=make('span','sx-card-selected','선택됨');
   card.type='button';card.dataset.example=item.id;card.setAttribute('aria-pressed','false');card.setAttribute('aria-label',item.title+' 예시 선택');
   image.src=url(item,playing?'animation':'poster');image.alt='';image.loading='lazy';image.dataset.style=item.style;badge.hidden=true;
   stage.append(image,make('span','sx-card-kind',item.effect==='none'?'동작 예시':'이펙트 포함'),badge);body.append(make('strong','',item.title),make('small','',item.description));card.append(stage,body);
   card.onclick=()=>{renderSelection(item);el('spriteExampleHero').scrollIntoView({behavior:playing?'smooth':'auto',block:'nearest'})};cards.set(item.id,card);el('spriteExampleCards').append(card);
  }
 }
 function applyFilter(next){
  if(assetType!=='side'||!categoryNames[next])return;
  filter=next;const visible=examples.filter(item=>category(item)===filter);
  root.dataset.category=filter;
  for(const item of examples)cards.get(item.id).hidden=!visible.includes(item);
  for(const button of root.querySelectorAll('[data-sprite-filter]'))button.setAttribute('aria-pressed',String(button.dataset.spriteFilter===filter));
  el('spriteLibraryTitle').textContent=categoryNames[filter]+' 동작 라이브러리';
  el('spriteCategoryEmpty').hidden=visible.length>0;
  root.querySelector('.sx-library-head').hidden=!visible.length;el('spriteExampleCards').hidden=!visible.length;root.querySelector('.sx-library-note').hidden=!visible.length;
  el('spriteExamplePlayback').hidden=!visible.length;root.querySelector('.sx-disclaimer').hidden=!visible.length;
  el('applyChibiCombat').hidden=filter!=='pixel';
  if(visible.length){
   if(!visible.includes(selected))renderSelection(visible.find(x=>x.id==='pixel-energy')||visible[0]);
   else renderSelection(selected);
  }else{
   selected=null;el('spriteExampleDetail').hidden=true;el('spriteExampleHero').removeAttribute('src');el('spriteExampleReference').removeAttribute('src');el('spriteExampleStatus').textContent='';
  }
 }
 function apply(){
  if(assetType!=='side'||!selected||category(selected)!==filter)return;
  try{
   const p={...selected.recipe};
   if(p.removeBackground&&(['ai','ai-sparks','ai-smooth','ai-soft'].includes(p.backgroundRemoval)||p.combatEffect==='subtle')&&el('backgroundRemoval').querySelector('[value="ai"]').dataset.ready==='false')throw Error('AI 배경 제거가 아직 준비되지 않았어요. 준비 후 이 설정을 적용해 주세요.');
   if(p.workflowId==='fasth3-sprite'&&!workflowStates.some(x=>x.id===p.workflowId&&x.ready))throw Error('이 일러스트 동작의 생성 설정이 아직 준비되지 않았어요. 잠시 후 다시 시도하거나 도트 예시를 선택해 주세요.');
   if(!p.prompt)p.prompt=presets[p.animationType]+(p.pixelOutput?'. Preserve the reference pixel art, head and body proportions, face, costume, one rigid existing weapon and square pixel clusters. No new scenery or camera movement.':'');
   p.assetSpec={type:'side',facing:['front','right','left','back'].includes(p.facing)?p.facing:p.animationType==='idle'?'front-right':'right',directionCount:1};
   window.applyRecreatePreset(p);el('facing').value=p.facing;el('settingCollection').value='';
   backgroundControls();updateButtonText();markApplied(selected.id);
   el('spriteExampleStatus').textContent=selected.title+' 설정을 적용했어요. 왼쪽에 내 이미지를 넣고 생성하세요.';
   el('message').textContent=el('spriteExampleStatus').textContent;
   if(matchMedia('(max-width:700px)').matches)window.spriteWorkspace?.mobileView('settings');
  }catch(error){el('spriteExampleStatus').textContent=error.message}
 }
 function syncType(value=window.assetStart?.current?.()){
  assetType=value?.type||null;
  const side=assetType==='side';root.dataset.assetType=assetType||'unselected';
  for(const node of [root.querySelector('.sx-category-picker'),el('spriteExamplePlayback'),root.querySelector('.sx-disclaimer'),root.querySelector('.sx-library-head'),el('spriteExampleCards'),root.querySelector('.sx-library-note'),summary])node.hidden=!side;
  el('applyChibiCombat').hidden=!side||filter!=='pixel';el('spriteCategoryEmpty').hidden=true;
  guide.hidden=side;
  if(side){
   el('spriteExamplesTitle').textContent='측면 캐릭터를 어떻게 움직일까요?';
   el('spriteExamplesTitle').nextElementSibling.textContent='측면 동작 예시 선택 → 내 캐릭터에 설정 적용 → 이미지 넣고 생성';
   if(examples.length)applyFilter(filter);
  }else{
   selected=null;applied='';summaryImage.hidden=true;summaryTitle.textContent='동작을 보고 골라 보세요';summaryNote.textContent='오른쪽에서 움직이는 예시와 시트를 비교합니다.';
   el('spriteExampleDetail').hidden=true;el('spriteExampleHero').removeAttribute('src');el('spriteExampleReference').removeAttribute('src');el('spriteExampleStatus').textContent='';
   const labels={illustration:['일러스트','캐릭터 원화의 구도와 그림체를 확인하는 유형이에요. 현재 등록된 측면 전투 동작 예시는 여기에 표시하지 않습니다.'],live2d:['Live2D 정면 원화','눈·입·머리카락을 나누어 움직이기 위한 정면 원화예요. 정면을 보는 입력을 준비하고, 눈·입 지정과 리깅은 2D 리깅에서 진행하세요.'],topdown:['탑다운 스프라이트','위에서 내려다보는 탐험·전투 시점이에요. 이 시점에 맞는 입력을 준비하세요. 등록된 탑다운 동작 예시는 아직 없습니다.'],isometric:['아이소메트릭 스프라이트','대각선 위에서 내려다보는 시점이에요. 이 시점에 맞는 입력을 준비하세요. 등록된 아이소메트릭 동작 예시는 아직 없습니다.']};
   const info=labels[assetType];el('spriteExamplesTitle').textContent=info?'선택한 에셋의 시점 안내':'먼저 에셋 유형을 골라 주세요';
   el('spriteExamplesTitle').nextElementSibling.textContent='선택한 유형에 맞는 예시와 안내만 보여드립니다.';
   guideTitle.textContent=info?.[0]||'어떤 에셋을 만들까요?';guideText.textContent=info?.[1]||'왼쪽에서 유형을 선택하면 해당 시점의 예시와 안내를 볼 수 있어요.';
   const card=assetType?document.querySelector(`input[name="assetType"][value="${assetType}"]`)?.closest('.asset-type-card'):null;
   const image=card?.querySelector('.asset-type-preview img');guideImage.hidden=!image;
   if(image)guideImage.src=image.getAttribute('src');else guideImage.removeAttribute('src');
   guideBadge.textContent=card?.querySelector('.asset-type-preview>span')?.textContent||'에셋 유형 선택';
  }
  el('spriteExampleLoading').hidden=!side||examples.length>0;
 }
 window.addEventListener('asset-type-change',event=>syncType(event.detail));
 el('spriteExampleApply').onclick=apply;
 el('spriteExamplePlayback').onclick=()=>{playing=!playing;syncPlayback()};
 el('spriteExampleMotion').onclick=()=>setView('motion');el('spriteExampleSheet').onclick=()=>setView('sheet');
 el('spriteExampleBackground').onchange=()=>{root.dataset.background=el('spriteExampleBackground').value};
 for(const button of root.querySelectorAll('[data-sprite-filter]'))button.onclick=()=>applyFilter(button.dataset.spriteFilter);
 for(const id of ['action','combatEffect','effectStrength','effectDescription','pixelOutput','prompt','duration','frames','facing','motionSpeed','trimAction']){
  el(id).addEventListener('input',()=>{if(applied){applied='';summaryTitle.textContent='직접 조정한 동작 설정';summaryNote.textContent='선택한 예시에서 설정을 수정했어요.';el('spriteExampleStatus').textContent=''}});
 }
 async function load(){
  try{const response=await fetch('assets/sprite-examples/catalog.json');if(!response.ok)throw Error('예시를 불러오지 못했어요.');const data=await response.json();examples=data.examples;if(!examples?.length)throw Error('등록된 예시가 없습니다.');
   renderCards();syncType();syncPlayback();el('spriteExampleLoading').hidden=true;
  }catch(error){el('spriteExampleLoading').textContent=error.message+' ';const retry=make('button','','다시 불러오기');retry.type='button';retry.onclick=load;el('spriteExampleLoading').append(retry)}
 }
 syncType();load();
})();
