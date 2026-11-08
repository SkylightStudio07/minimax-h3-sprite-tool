/* Visual presets are separate from character text, so switching never stacks style prompts. */
(()=>{
 const el=id=>document.getElementById(id);
 let catalog=null,active='',pending=null;
 const pager=window.createImageLibraryPager(el('lookCards'),'lookPagination');
 const names={'wai-cutscene-counter':'WAI17 · Cutscene + 전투 형식','anima-base':'Anima Base 1.0','soya-anima-flanime':'Soya · Anima → Flanime','anima-turbo':'Anima Turbo','animagine-xl':'Animagine XL','illustrious-xl':'Illustrious XL','flanime-xl':'Flanime · 원본 고해상도'};
 function available(look){
  if(!models.some(m=>m.id===look.model&&m.ready)||window.imageLookAllowed&&!window.imageLookAllowed(look))return false;
  if(!look.styleId)return true;
  return window.imageStyleAvailable?.(look.styleId,models.find(m=>m.id===look.model)?.family||(look.model==='animagine-xl'?'sdxl':'anima'))||false;
 }
 function activeNote(){
  const look=catalog?.looks.find(x=>x.id===active);
  el('lookActive').textContent=look?'적용 중: '+look.name+' · 캐릭터 설명과 별도로 적용됩니다. 세부 설정은 고급 설정에서 조절할 수 있어요.':'적용 중인 그림체 프리셋이 없어요.';
  el('lookClear').disabled=!look;
 }
 function apply(look){
  if(!available(look))return;
  const mode=el('mode').value,saved={denoise:el('denoise').value,count:el('count').value,pose:window.imagePosePayload?.(),asset:window.assetStart?.payload().assetSpec};
  const restoreInput=()=>{if(mode==='text')return;el('mode').value=mode;el('mode').dispatchEvent(new Event('change'));el('denoise').value=saved.denoise;el('count').value=saved.count;el('faceDetail').checked=false;window.restoreImagePose?.(saved.pose||{});if(saved.asset)window.assetStart?.restore(saved.asset)};
  if(look.recipePreset){window.applyCutsceneRecipe?.();restoreInput();return}
  const switched=el('model').value!==look.model;el('model').value=look.model;if(switched)el('model').dispatchEvent(new Event('change'));
  if(look.sheetPreset)window.applyRpgSheet?.(look.styleId);
  window.restoreImageStyle({styleId:look.styleId,styleStrength:look.styleStrength});
  el('steps').value=look.steps;el('cfg').value=look.cfg;
  active=look.id;activeNote();restoreInput();
 }
 function render(reset=false){
  if(!catalog)return;
  const query=el('lookSearch').value.trim().toLowerCase(),group=el('lookGroup').value;
  const visible=catalog.looks.filter(x=>x.listed!==false&&(!window.imageLookAllowed||window.imageLookAllowed(x)));
  const list=visible.filter(x=>(group?(group==='soya'?x.model==='soya-anima-flanime':x.group===group):!x.experimental)&&(!query||[x.id,x.name,x.prompt,x.note||'',x.styleId||''].join(' ').normalize('NFKC').toLowerCase().includes(query.normalize('NFKC'))));
  el('lookCards').replaceChildren();el('lookCount').textContent=`전체 ${visible.length}개 중 ${list.length}개 · 실제 생성한 예시만 표시합니다. 프리셋은 캐릭터를 고정하지 않습니다.`;
  for(const look of list){
   const card=document.createElement('article');card.className='look-card';card.dataset.model=look.model;
   const title=document.createElement('h4');title.textContent=look.name;
   const settings=document.createElement('p');settings.className='muted';
   settings.textContent=`${names[look.model]} · ${(look.styleId?window.imageStyleName?.(look.styleId):'')||(look.model==='soya-anima-flanime'?'Kieed 기본 조합':'LoRA 없음')}${look.styleId?' '+look.styleStrength:''} · ${look.steps} steps / CFG ${look.cfg}`;
   card.append(title);
   const previews=look.previews|| (look.preview?[{url:look.preview,label:'실제 생성 예시'}]:[]);
   for(const preview of previews){const a=document.createElement('a');a.href=new URL(preview.url,location.href).href;a.target='_blank';a.rel='noopener';const img=document.createElement('img');img.src=a.href;img.alt=look.name+' · '+preview.label;img.loading='lazy';a.append(img);card.append(a)}

   if(!previews.length){const waiting=document.createElement('p');waiting.className='muted';waiting.textContent='실제 생성 예시 준비 중';card.append(waiting)}
   const note=document.createElement('p');note.className='muted';note.textContent=look.verification+(look.note?' · '+look.note:'');
   const detail=document.createElement('details'),summary=document.createElement('summary'),text=document.createElement('p');summary.textContent='설명·출처·세부 설정 보기';text.textContent=look.prompt+' / 제외: '+look.negative;detail.append(summary,settings,text);
   const use=document.createElement('button');use.type='button';use.className='ui-btn ui-btn--sm';use.dataset.useLook=look.id;use.disabled=!available(look);use.textContent=use.disabled?'아직 사용할 수 없어요':'이 그림체 적용';use.onclick=()=>apply(look);
   detail.append(note);card.append(detail,use);el('lookCards').append(card);
  }pager.setItems([...el('lookCards').children],reset===true);
 }
 el('lookGroup').onchange=()=>render(true);el('lookSearch').oninput=()=>render(true);
 el('lookClear').onclick=()=>{active='';activeNote()};
 el('model').addEventListener('change',()=>{if(active&&catalog?.looks.find(x=>x.id===active)?.model!==el('model').value){active='';activeNote()}});
 window.imageLookPayload=()=>({lookId:active});
 window.restoreImageLook=settings=>{if(!catalog){pending=settings;return}active=catalog.looks.some(x=>x.id===settings.lookId&&x.model===settings.model)?settings.lookId:'';activeNote()};
 window.addEventListener('image-styles-ready',render);
 window.addEventListener('image-models-ready',render);
 fetch(new URL('assets/image-looks.json',location.href)).then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{
  catalog=data;for(const g of data.groups)el('lookGroup').add(new Option(g.name,g.id));el('lookGroup').value=data.groups.some(g=>g.id==='soya')?'soya':data.groups.some(g=>g.id==='artist')?'artist':'flat';render();activeNote();if(pending){window.restoreImageLook(pending);pending=null}
 }).catch(()=>{el('lookCount').textContent='그림체 프리셋을 불러오지 못했어요. 새로고침해 주세요.'});
})();
