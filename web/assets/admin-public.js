/* 관리 · 공개 Live2D. Shell helpers ($, node, api, toast, uiDialog, fmtDate) come from team.html/results.js. */
async function loadAdminPublic(){
  const body=$('publicAdminRows'),empty=$('publicAdminEmpty');
  let items;
  try{items=(await api('api/admin/public-live2d')).items}catch(error){toast(error.message,{tone:'danger'});return}
  empty.hidden=items.length>0;
  body.replaceChildren(...items.map(item=>{
    const row=document.createElement('tr');
    const cell=child=>{const td=document.createElement('td');td.append(child);return td};
    const open=node('a',item.title);open.href=item.url.replace(/^\//,'');open.target='_blank';open.rel='noopener';
    const source=node('a','결과 상세');source.href='#/jobs/'+item.jobId;
    const state=node('span',item.stale?'공개본이 오래됨':'최신','ui-badge '+(item.stale?'ui-badge--warning':'ui-badge--success'));
    const actions=document.createElement('td');actions.className='cell-actions';
    const update=node('button','공개본 갱신','ui-btn ui-btn--sm'+(item.stale?' ui-btn--primary':''));update.type='button';
    update.onclick=()=>act(item,'publish',update);
    const remove=node('button','내리기','ui-btn ui-btn--sm ui-btn--danger');remove.type='button';
    remove.onclick=()=>act(item,'unpublish',remove);
    actions.append(update,' ',remove);
    row.append(cell(open),cell(source),cell(node('span',item.owner||'-')),cell(node('span',fmtDate(item.updated))),cell(state),actions);
    return row;
  }));
}
async function act(item,action,button){
  const publish=action==='publish';
  const ok=await uiDialog({title:publish?`'${item.title}' 공개본을 갱신할까요?`:`'${item.title}'을 내릴까요?`,
    body:publish?'현재 저장된 버전이 로그인 없이 공개됩니다.':'외부 접근이 바로 차단됩니다. 복제 파일은 서버에 보관됩니다.',
    confirmLabel:publish?'갱신':'내리기',danger:!publish});
  if(!ok)return;
  button.disabled=true;
  try{await api('api/jobs/'+item.jobId+'/public-live2d',{action,title:item.title});toast(publish?'공개본을 갱신했습니다.':'공개 Live2D를 내렸습니다.',{tone:'success'});await loadAdminPublic()}
  catch(error){toast(error.message,{tone:'danger'});button.disabled=false}
}
