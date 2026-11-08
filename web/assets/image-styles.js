(()=>{
 const el=id=>document.getElementById(id);let styles=[],installed=[],pendingRestore=null;
 const searchLabel=document.createElement('label');searchLabel.textContent='그림체 검색';const search=document.createElement('input');search.id='styleSearch';search.type='search';search.className='ui-input';search.placeholder='이름, 작가, 선·채색 느낌…';searchLabel.append(search);el('styleCards').before(searchLabel);
 const pager=window.createImageLibraryPager(el('styleCards'),'stylePagination');
 function filterStyles(reset=false){const query=search.value.trim().normalize('NFKC').toLowerCase();pager.setItems([...el('styleCards').children].filter(card=>card.dataset.search.includes(query)),reset)}
 search.oninput=()=>filterStyles(true);
 const label=document.createElement('label');label.textContent='추가 그림체';label.hidden=true;
 const select=document.createElement('select');select.id='styleId';select.className='ui-input';select.add(new Option('사용 안 함',''));label.append(select);
 const strengthLabel=document.createElement('label');strengthLabel.className='style-strength-setting';strengthLabel.textContent='추가 그림체 반영 정도';strengthLabel.hidden=true;const strengthValue=document.createElement('output');strengthValue.htmlFor='styleStrength';const strength=document.createElement('input');strength.id='styleStrength';strength.className='ui-input';strength.type='range';strength.min=0;strength.max=1.2;strength.step=.05;strength.value=.7;strength.disabled=true;strengthLabel.append(strengthValue,strength);const showStrength=()=>{strengthValue.textContent=Math.round(Number(strength.value)*100)+'%'};strength.addEventListener('input',showStrength);showStrength();
 if(el('styleSettingControls'))el('styleSettingControls').append(label,strengthLabel);else el('modelSource').parentElement.after(label,strengthLabel);
 const rights=document.createElement('dialog');rights.id='artistRightsDialog';rights.setAttribute('aria-labelledby','artistRightsTitle');rights.style.cssText='position:fixed;inset:24px 0 auto;margin:0 auto;max-height:calc(100dvh - 48px);overflow:auto;max-width:520px;width:calc(100% - 48px);box-sizing:border-box;padding:24px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2,#202630);color:var(--text,#eee)';
 const rightsTitle=document.createElement('h3');rightsTitle.id='artistRightsTitle';rightsTitle.textContent='작가 화풍 · 이용 안내';
 const rightsArtist=document.createElement('p');const rightsText=document.createElement('p');rightsText.textContent='이 그림체는 특정 작가의 화풍을 참고한 생성 설정입니다. 레퍼런스와 화풍 연구용으로 활용하고, 생성 결과를 그대로 게임 개발의 최종 아트로 사용하는 것은 권장하지 않습니다.';
 const rightsDetail=document.createElement('p');rightsDetail.textContent='모델의 이용 허용 조건만으로 생성물의 권리 문제가 모두 해결되는 것은 아닙니다. 게임에 사용하기 전에는 원작과의 유사성, 캐릭터·로고 등 포함 요소와 이용 조건을 확인하고 필요한 허락을 받으세요.';
 const rightsLink=document.createElement('a');rightsLink.target='_blank';rightsLink.rel='noopener noreferrer';rightsLink.textContent='모델 출처·이용 조건 확인';
 const rightsClose=document.createElement('button');rightsClose.type='button';rightsClose.className='ui-btn';rightsClose.textContent='닫기';rightsClose.style.cssText='display:block;margin-top:20px';rightsClose.onclick=()=>rights.close();rights.append(rightsTitle,rightsArtist,rightsText,rightsDetail,rightsLink,rightsClose);document.body.append(rights);
 function showArtistRights(style){if(!style?.artistName)return;rightsArtist.textContent='참고 작가: '+style.artistName;rightsLink.href=style.source;if(!rights.open)rights.showModal()}
 const css=document.createElement('style');css.textContent='.style-examples{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}.style-examples img{width:100%;aspect-ratio:3/4;object-fit:contain;background:var(--surface-2);border-radius:8px}.style-card{border-bottom:1px solid var(--line);padding:16px 0}.style-card:last-child{border:0}@media(max-width:500px){.style-examples{grid-template-columns:repeat(2,minmax(0,1fr))}}';document.head.append(css);
 window.showImageArtistRights=showArtistRights;
 function family(m){return m?.family||(m?.id==='animagine-xl'?'sdxl':m?.id?.includes('anima')?'anima':'illustrious')}
 function targetFor(s){
  if(el('model').value==='pixel-art-xl')return {reason:'픽셀 전용 세팅은 고정 그림체를 사용합니다. 일반 이미지 작업에서 추가 그림체를 선택하세요.'};
  if(!s.enabled)return {reason:'제작자가 공개한 파일의 설치·검증을 기다리는 그림체예요.'};
  if(!installed.includes(s.id))return {reason:'그림체 파일이 아직 설치되지 않았어요. 다른 그림체를 골라주세요.'};
  if(s.sheetPreset)return {sheet:true};
  if(el('preset').value==='rpg-sheet')return {reason:'4방향 시트는 전용 그림체를 사용해요. 새 이미지 만들기에서 이 그림체를 선택하세요.'};
  const mode=el('mode').value,current=models.find(m=>m.id===el('model').value);
  const usable=m=>m.ready&&m.id!=='wai-cutscene-counter'&&family(m)===s.family&&(m.modes||['text','reference','inpaint']).includes(mode)&&(!el('poseEnabled')?.checked||(window.imagePoseState?.models||[]).includes(m.id));
  const preferred=s.family==='illustrious'?['flanime-xl','illustrious-xl']:s.family==='sdxl'?['animagine-xl']:['soya-anima-flanime','anima-turbo','anima-base'];
  const target=usable(current||{})?current:preferred.map(id=>models.find(m=>m.id===id)).find(m=>m&&usable(m));
  return target?{model:target,switching:current?.id!==target.id}:{reason:el('poseEnabled')?.checked?'이 그림체는 현재 자세 고정을 지원하지 않아요. 자세 적용을 끄거나 다른 그림체를 골라주세요.':'현재 작업에서 쓸 수 있는 생성 설정이 없어요. 새 이미지 만들기에서 선택하거나 다른 그림체를 골라주세요.'};
 }
 function refresh(){
  for(const option of select.options){if(!option.value)continue;const s=styles.find(x=>x.id===option.value),target=targetFor(s);option.disabled=Boolean(target.reason);option.textContent=s.name+(target.reason?' · 사용 불가':target.switching?' · 설정 전환':'')}
  const chosen=styles.find(s=>s.id===select.value),current=models.find(m=>m.id===el('model').value);if(select.selectedOptions[0]?.disabled||chosen&&current&&(family(current)!==chosen.family||current.id==='wai-cutscene-counter')){select.value='';const feedback=el('styleSelectionStatus');if(feedback)feedback.textContent='기본 그림체가 바뀌어 추가 그림체를 해제했어요. 다시 선택할 수 있습니다.'}strength.disabled=!select.value;
  strengthLabel.hidden=!select.value;showStrength();
  el('styleNotice').textContent='사용할 그림체를 고르면 필요한 기본 설정도 맞춰집니다. 전환이 필요한 항목은 카드에 표시해요. 캐릭터 설명과 업로드한 이미지는 유지합니다.';
  document.querySelectorAll('[data-use-style]').forEach(b=>{const s=styles.find(x=>x.id===b.dataset.useStyle),target=targetFor(s);b.disabled=Boolean(target.reason);b.textContent=target.reason?'사용 불가':target.switching?'설정 전환 후 적용':'이 그림체 적용';b.title=target.reason||'';const note=b.closest('.style-card').querySelector('.style-availability');if(note){note.textContent=target.reason||(target.switching?'기본 설정을 '+(target.model.name||'호환 그림체')+'로 바꿔 적용해요.':'현재 설정에서 바로 적용할 수 있어요.');note.dataset.available=String(!target.reason)}});
 }
 function applyStyle(s){
  if(!s){window.restoreImageLook?.({});select.value='';strength.disabled=true;refresh();window.dispatchEvent(new Event('image-style-changed'));return}
  const target=targetFor(s);if(target.reason){el('styleNotice').textContent=target.reason;return}
  if(target.sheet){window.applyRpgSheet?.(s.id);return}
  window.restoreImageLook?.({});
  if(target.switching){el('model').value=target.model.id;el('model').dispatchEvent(new CustomEvent('change',{detail:{assetSetup:true}}))}
  select.value=s.id;strength.value=s.strength;refresh();
  const message=s.name+' 적용'+(target.switching?' · 호환되는 기본 설정으로 전환했어요.':'');el('styleNotice').textContent=message;const feedback=el('styleSelectionStatus');if(feedback)feedback.textContent=message;
  window.dispatchEvent(new Event('image-style-changed'));showArtistRights(s);
 }
 select.onchange=()=>applyStyle(styles.find(s=>s.id===select.value));el('model').addEventListener('change',refresh);window.addEventListener('image-models-ready',refresh);el('mode').addEventListener('change',refresh);el('poseEnabled').addEventListener('change',refresh);
 window.imageStyleName=id=>styles.find(s=>s.id===id)?.name||'선택한 화풍';
 window.imageStyleAvailable=(id,family)=>styles.some(s=>s.id===id&&s.family===family&&s.enabled&&installed.includes(id));
 window.imageStylePayload=()=>({styleId:select.value,styleStrength:Number(strength.value)});
 window.imageStylePreview=()=>{const chosen=styles.find(s=>s.id===select.value);return chosen?{name:chosen.name,preview:chosen.previews?.[0]?.url}:null};
 window.restoreImageStyle=s=>{if(!styles.length){pendingRestore=s;return}select.value=s.styleId||'';strength.value=s.styleStrength??.7;refresh();showArtistRights(styles.find(s=>s.id===select.value));window.dispatchEvent(new Event('image-style-changed'))};
 Promise.all([fetch(new URL('assets/image-styles.json',location.href)).then(r=>{if(!r.ok)throw Error();return r.json()}),(window.imageModelsRequest||api('api/images/models'))]).then(([data,state])=>{
  styles=data.styles;installed=(state.styles||[]).filter(s=>s.installed).map(s=>s.id);
  for(const s of styles){select.add(new Option(s.name+(s.enabled?'':' · 검증 대기'),s.id));const card=document.createElement('article');card.className='style-card';const title=document.createElement('h4');title.textContent=s.name;const desc=document.createElement('p');desc.textContent=s.description.replace(/\bLoRA\b/g,'추가 그림체');const gallery=document.createElement('div');gallery.className='style-examples';
   for(const [i,p] of s.previews.entries()){const a=document.createElement('a');a.href=new URL(p.source,location.href).href;a.target='_blank';a.rel='noopener noreferrer';const img=document.createElement('img');img.src=new URL(p.url,location.href).href;img.alt=`${s.name} ${p.label||'제작자 예시'} ${i+1}`;img.loading='lazy';img.referrerPolicy='no-referrer';img.onerror=()=>{img.remove();a.textContent=`예시 ${i+1} · 출처에서 보기`};a.append(img);gallery.append(a)}
   const note=document.createElement('p');note.className='muted';note.textContent=`${installed.includes(s.id)?'설치됨':'미설치'} · ${s.family} · 기본 강도 ${s.strength} · ${s.creator} · ${s.verification} · ${typeof s.license==='string'?s.license:'제작자 이용 조건 확인'}`;const link=document.createElement('a');link.href=s.source;link.target='_blank';link.rel='noopener noreferrer';link.textContent='제작자·이용 조건';const trigger=document.createElement('p');trigger.className='muted';trigger.textContent='자동 적용 트리거: '+(s.triggers.join(', ')||'없음');const use=document.createElement('button');use.type='button';use.className='ui-btn ui-btn--sm';use.dataset.useStyle=s.id;use.textContent=s.enabled?'이 그림체 사용':'설치·검증 후 사용 가능';use.onclick=()=>applyStyle(s);const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='출처·이용 조건·세부 설정';details.append(summary,note,link,trigger);const availability=document.createElement('p');availability.className='style-availability';availability.setAttribute('role','status');card.append(title,desc,gallery,details,availability,use);
   if(s.artistName){const notice=document.createElement('button');notice.type='button';notice.className='ui-btn ui-btn--sm';notice.dataset.artistRights=s.id;notice.textContent='작가 화풍 · 이용 안내';notice.onclick=()=>showArtistRights(s);card.append(notice)}el('styleCards').append(card);
  }for(const [i,card] of [...el('styleCards').children].entries()){const s=styles[i];card.dataset.search=[s.id,s.name,s.description,s.artistName||'',s.creator,s.family,...s.triggers].join(' ').normalize('NFKC').toLowerCase()}filterStyles();refresh();window.dispatchEvent(new Event('image-styles-ready'));if(pendingRestore){window.restoreImageStyle(pendingRestore);pendingRestore=null}
 }).catch(()=>{el('styleNotice').textContent='그림체 목록을 불러오지 못했어요. 새로고침해 주세요.'});
})();
