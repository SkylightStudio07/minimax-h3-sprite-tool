/* Shared by studio candidates and gallery details. Only saved, authorized images. */
(()=>{
 const css=document.createElement('link');css.rel='stylesheet';css.href='/assets/image-face-refine.css';document.head.append(css);
 const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e};
 const dialog=el('dialog',null,'face-refine-dialog');dialog.id='faceRefineDialog';dialog.setAttribute('aria-labelledby','faceRefineTitle');
 const title=el('h2','얼굴만 보정');title.id='faceRefineTitle';const close=el('button','닫기','ui-btn');close.type='button';
 const head=el('div',null,'face-refine-head');head.append(title,close);
 const intro=el('p','얼굴을 찾아 확대해 다듬고 원래 위치에 합칩니다. 원본 크기와 투명도는 유지하며, 보정본은 새 결과로 저장해요.');
 const note=el('p',null,'muted');note.id='faceRefineNote';
 const label=el('label','보정 정도'),strength=el('select',null,'ui-input');strength.id='faceRefineStrength';strength.add(new Option('약하게 · 원래 인상 유지 (0.12)','0.12'));strength.add(new Option('더 선명하게 · 인상이 달라질 수 있음 (0.20)','0.20'));label.append(strength);
 const message=el('p',null,'face-refine-status');message.id='faceRefineStatus';message.setAttribute('role','status');message.setAttribute('aria-live','polite');
 const submit=el('button','얼굴 보정 시작','ui-btn ui-btn--primary');submit.type='button';submit.id='startFaceRefine';
 const comparison=el('div',null,'face-refine-comparison');comparison.id='faceRefineComparison';comparison.hidden=true;
 const links=el('div',null,'face-refine-links');
 dialog.append(head,intro,note,label,submit,message,comparison,links);document.body.append(dialog);
 let current=null,pending=false,timer=null,ticket=0;
 async function json(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Sprite-Request':'1'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'요청 실패');return d}
 close.onclick=()=>dialog.close();dialog.addEventListener('close',()=>{clearTimeout(timer);ticket++});
 function reset(){clearTimeout(timer);ticket++;comparison.replaceChildren();comparison.hidden=true;links.replaceChildren();message.textContent='';submit.hidden=false;submit.disabled=false;strength.disabled=false;strength.value='0.12';label.hidden=false;pending=false;}
 function link(text,path,download=false){const a=el('a',text,'ui-btn ui-btn--sm');a.href=path;if(download)a.download='face-refined.png';else{a.target='_blank';a.rel='noopener'}links.append(a)}
 async function showComparison(job,image){
  reset();title.textContent='얼굴 보정 전후 비교';intro.textContent='얼굴 주변을 확대해 비교하세요. 보정본은 별도 결과이며 원본도 유지됩니다.';label.hidden=true;submit.hidden=true;note.textContent='';
  message.textContent=image.warning||'왼쪽 원본 · 오른쪽 보정본';comparison.hidden=false;const mark=ticket;
  const crop=image.faceBox;const padding=crop?Math.max(24,Math.round(Math.max(crop[2]-crop[0],crop[3]-crop[1])*.35)):0;
  for(const [text,path] of [['원본',image.beforeFaceUrl],['보정본',image.url]]){
   const figure=el('figure'),caption=el('figcaption',text),canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',text+' 얼굴 확대');figure.append(caption,canvas);comparison.append(figure);
   const im=new Image();await new Promise((resolve,reject)=>{im.onload=resolve;im.onerror=()=>reject(Error('비교 이미지를 불러오지 못했습니다.'));im.src=path});if(mark!==ticket)return;
   const box=crop?[Math.max(0,crop[0]-padding),Math.max(0,crop[1]-padding),Math.min(im.width,crop[2]+padding),Math.min(im.height,crop[3]+padding)]:[0,0,im.width,im.height];
   canvas.width=box[2]-box[0];canvas.height=box[3]-box[1];canvas.getContext('2d').drawImage(im,...[box[0],box[1],canvas.width,canvas.height],0,0,canvas.width,canvas.height);
  }
  link('보정 PNG 저장',image.url,true);link('원본 전체 보기',image.beforeFaceUrl);link('보정본 전체 보기',image.url);
  const jid=job.id||image.url.split('/')[3];link('갤러리 결과 보기','/#/jobs/'+jid);
 }
 async function poll(id,mark){
  try{const job=await json('/api/jobs/'+id);if(mark!==ticket||!dialog.open)return;
   message.textContent=job.message||'얼굴 보정 작업 중…';
   if(job.state==='complete'){await showComparison(job,job.images[0]);return}
   if(['error','cancelled'].includes(job.state)){pending=false;submit.disabled=false;strength.disabled=false;return}
  }catch(e){if(mark===ticket)message.textContent='상태 연결을 다시 확인하고 있어요. 작업을 중복 등록하지 않습니다.'}
  if(mark===ticket&&dialog.open)timer=setTimeout(()=>poll(id,mark),2500);
 }
 submit.onclick=async()=>{
  if(pending||!current)return;pending=true;submit.disabled=true;strength.disabled=true;message.textContent='팀 대기열에 등록 중…';
  const target=current,mark=ticket;
  try{const r=await json('/api/images/'+target.id+'/face-refine',{image:target.index,strength:Number(strength.value)});
   if(target.onQueued){dialog.close();target.onQueued(r.jobId)}else if(mark===ticket&&dialog.open){message.textContent='얼굴 보정 대기 중 · 이 창을 닫아도 작업은 계속됩니다. 결과는 내 작업에서도 확인할 수 있어요.';poll(r.jobId,mark)}
  }catch(e){if(mark===ticket){message.textContent=e.message;pending=false;submit.disabled=false;strength.disabled=false}}
 };
 window.imageFaceRefine={
  open:async(job,image,options={})=>{
   if(dialog.open&&pending)return;
   const match=/^\/api\/images\/([a-f0-9]{32})\/image-([1-4])\.png$/.exec(image.url);if(!match)throw Error('저장된 원화 결과에서 선택하세요.');
   reset();current={id:match[1],index:Number(match[2])-1,...options};title.textContent='얼굴만 보정';intro.textContent='얼굴을 찾아 확대해 다듬고 원래 위치에 합칩니다. 원본 크기와 투명도는 유지하며, 보정본은 새 결과로 저장해요.';
   const m=job.settings?.model||job.model;note.textContent=['illustrious-xl','animagine-xl','flanime-xl','wai-cutscene-counter'].includes(m)?'선택한 결과의 기본 그림체로 얼굴을 보정합니다. 눈 모양·표정은 전후를 비교해 확인하세요.':'일러스트용 얼굴 보정 설정을 사용해요. 원래 그림체나 인상이 조금 달라질 수 있습니다.';
   if(!dialog.open)dialog.showModal();
  },
  compare:async(job,image)=>{if(!dialog.open)dialog.showModal();try{await showComparison(job,image)}catch(e){message.textContent=e.message}}
 };
})();
