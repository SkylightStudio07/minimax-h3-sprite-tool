/* Templates resolve to editable text; existing job/PNG metadata already preserves that text. */
(()=>{
 const el=id=>document.getElementById(id);let catalog,previous=null;
 function combo(){return catalog.combinations.find(c=>c.id===el('templateCombo').value)}
 function supportedSize(selected){const option=[...el('size').options].find(o=>o.value===selected?.size);return option&&!option.disabled?option.value:el('size').value}
 function rebuild(){
  if(!catalog)return;
  const family=['animagine-xl','illustrious-xl','flanime-xl'].includes(el('model').value)?'sdxl':'anima';
  const parts=catalog.categories.map(c=>c.items.find(i=>i.id===el('template-'+c.id).value)?.[family]).filter(Boolean);
  el('templatePreview').value=parts.join(family==='sdxl'?', ':' ');
  el('templateApply').disabled=!parts.length;
  const selected=combo();
  el('templateNote').textContent=(family==='sdxl'?'SDXL / Illustrious용 태그':'Anima용 문장')+' · 적용 시 용도: '+(selected?.preset==='live2d'?'Live2D 정면':'일반 일러스트')+(selected?' · 해상도 '+supportedSize(selected).replace('x','×'):' · 기존 해상도 유지')+'. 현재 워크플로에서 지원하는 해상도로 적용합니다.';
 }
 el('templatePreview').addEventListener('input',()=>{el('templateApply').disabled=!el('templatePreview').value.trim()});
 el('model').addEventListener('change',rebuild);
 el('templateApply').onclick=()=>{
  const addition=el('templatePreview').value.trim(),prompt=el('prompt').value.trim();if(!addition)return;
  if(prompt.includes(addition)){el('templateNote').textContent='이미 같은 문구가 설명에 있어요.';return}
  const next=[prompt,addition].filter(Boolean).join('\n');
  if(next.length>el('prompt').maxLength){el('templateNote').textContent='설명이 너무 길어요. 일부 문구를 줄여 주세요.';return}
  previous={before:el('prompt').value,preset:el('preset').value,size:el('size').value,after:next};
  el('prompt').value=next;el('preset').value=combo()?.preset||'illustration';if(combo())el('size').value=supportedSize(combo());
  previous.afterPreset=el('preset').value;previous.afterSize=el('size').value;
  el('templateUndo').disabled=false;el('templateNote').textContent='설명에 추가했어요. 내용을 직접 다듬고 생성하세요. 다른 조합을 비교하려면 먼저 추가 되돌리기를 누르세요.';
 };
 el('templateUndo').onclick=()=>{
  if(!previous)return;
  if(el('prompt').value!==previous.after||el('preset').value!==previous.afterPreset||el('size').value!==previous.afterSize){el('templateNote').textContent='추가 후 직접 수정한 내용이 있어 자동으로 되돌리지 않았어요. 설명에서 원하는 문구를 지워 주세요.';return}
  el('prompt').value=previous.before;el('preset').value=previous.preset;el('size').value=previous.size;previous=null;el('templateUndo').disabled=true;el('templateNote').textContent='추가 전 설명·용도·해상도로 되돌렸어요.';
 };
 fetch(new URL('assets/image-templates.json',location.href)).then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{
  catalog=data;
  for(const c of catalog.categories){const label=document.createElement('label'),select=document.createElement('select');label.textContent=c.label;select.id='template-'+c.id;select.className='ui-input';select.add(new Option('선택 안 함',''));for(const i of c.items)select.add(new Option(i.label,i.id));select.onchange=()=>{el('templateCombo').value='';rebuild()};label.append(select);el('templateChoices').append(label)}
  for(const c of catalog.combinations)el('templateCombo').add(new Option(c.label,c.id));
  el('templateCombo').onchange=()=>{const c=combo();for(const category of catalog.categories)el('template-'+category.id).value=c?.choices[category.id]||'';rebuild()};rebuild();
 }).catch(()=>{el('templateNote').textContent='템플릿을 불러오지 못했어요. 새로고침하거나 설명을 직접 입력해 주세요.'});
})();
