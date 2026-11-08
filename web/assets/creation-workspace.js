/* Shared creation layout. Move the existing nodes, preserving forms, canvas state and handlers. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id),main=document.querySelector('main');
 const kind=document.body.dataset.assetStudio==='image'?'image':$('maskPane')?'rig':document.body.dataset.assetStudio==='sprite'?'sprite':null;
 if(!kind||!main)return;
 const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n};
 const button=(text,run)=>{const b=node('button','ui-btn ui-btn--sm',text);b.type='button';b.onclick=run;return b};
 const names={image:'이미지 스튜디오',sprite:'스프라이트 만들기',rig:'2D 리깅 만들기'};
 document.documentElement.classList.add('creation-layout');document.body.classList.add('creation-studio');document.body.dataset.creationKind=kind;
 if(kind!=='image')document.documentElement.classList.add('embedded-studio');
 main.classList.add('creation-workspace');
 const toolbar=node('header','creation-toolbar'),title=node('h1','',names[kind]),mobile=node('div','creation-mobile-tabs');
 const settingsButton=button('설정',()=>mobileView('settings')),workButton=button('작업 화면',()=>mobileView('output'));
 mobile.setAttribute('aria-label','설정과 작업 화면 전환');mobile.append(settingsButton,workButton);toolbar.append(title,mobile);
 const layout=node('div','creation-layout-grid'),left=node('aside','creation-settings'),settings=node('div','creation-settings-scroll'),footer=node('div','creation-submit');
 left.setAttribute('aria-label','생성 설정');settings.tabIndex=0;left.append(settings,footer);
 const output=node('section','creation-output'),head=node('header','creation-output-header'),tabs=node('div','creation-output-tabs'),tools=node('div','creation-output-tools'),work=node('div','creation-output-scroll');
 output.setAttribute('aria-label','작업 화면과 생성 결과');work.tabIndex=0;head.append(tabs,tools);output.append(head,work);layout.append(left,output);
 main.append(toolbar,layout);
 let current='',candidates=[],candidate=0,display='gallery';const pages=new Map();
 function mobileView(value){main.dataset.mobileView=value;settingsButton.setAttribute('aria-pressed',String(value==='settings'));workButton.setAttribute('aria-pressed',String(value==='output'))}
 function show(id,focusMobile=false){if(!pages.has(id))return;current=id;for(const [key,p] of pages){p.host.hidden=key!==id;p.button.setAttribute('aria-pressed',String(key===id))}if(focusMobile)mobileView('output')}
 function page(id,label){const host=node('div','creation-page'),b=button(label,()=>{show(id);mobileView('output')});host.dataset.page=id;pages.set(id,{host,button:b});tabs.append(b);work.append(host);return host}
 function context(){const existing=$('creationCharacter')?.closest('.character-context-compact')||$('creationCharacter')?.closest('section');if(!existing)return;
  if(existing.matches('details')){settings.prepend(existing);return}
  const d=node('details','creation-character'),s=node('summary','','캐릭터 묶음에 저장 · 선택사항');d.append(s,existing);settings.prepend(d);
 }
 function empty(title,text){const box=node('div','creation-empty');box.append(node('span','creation-empty-icon',kind==='rig'?'◉':'▷'),node('h2','',title),node('p','',text));return box}
 if(kind==='image'){
  const form=$('form'),generateBar=form.querySelector('.generate-bar'),preview=$('studioPreview'),taskTabs=document.querySelector('.task-tabs');
  settings.append(taskTabs,form);footer.append(generateBar);$('generate').setAttribute('form','form');
  toolbar.append($('libraryToggle'));
  const resultsPage=page('results','생성 결과'),referencePage=page('reference','원본 · 부분 수정');
  resultsPage.append($('resultPanel'));referencePage.append($('referencePanel'));
  const hint=$('workspaceHint')?.closest('.next-step');if(hint)resultsPage.prepend(hint);
  const gallery=button('후보 목록',()=>setDisplay('gallery')),stage=button('크게 보기',()=>setDisplay('stage'));
  gallery.setAttribute('aria-label','후보 목록으로 보기');stage.setAttribute('aria-label','선택한 후보 크게 보기');
  const prev=button('←',()=>choose(candidate-1)),next=button('→',()=>choose(candidate+1)),count=node('span','creation-candidate-count');
  prev.setAttribute('aria-label','이전 후보');next.setAttribute('aria-label','다음 후보');tools.append(gallery,stage,prev,count,next);
  function choose(index){candidate=Math.max(0,Math.min(candidates.length-1,index));candidates.forEach((c,i)=>c.classList.toggle('creation-selected',i===candidate));count.textContent=candidates.length?`${candidate+1} / ${candidates.length}`:'0개';prev.disabled=!candidates.length||candidate===0;next.disabled=!candidates.length||candidate===candidates.length-1}
  function setDisplay(value){display=value;resultsPage.dataset.display=value;gallery.setAttribute('aria-pressed',String(value==='gallery'));stage.setAttribute('aria-pressed',String(value==='stage'));choose(candidate);show('results')}
  $('results').addEventListener('click',event=>{if(display==='gallery'&&event.target.matches('article > img')){candidate=candidates.indexOf(event.target.closest('article'));event.preventDefault();event.stopImmediatePropagation();setDisplay('stage')}},true);
  new MutationObserver(()=>{candidates=[...$('results').children];choose(0);if(candidates.length){show('results',true)}}).observe($('results'),{childList:true});
  const syncReference=()=>{const available=!$('referencePanel').hidden;pages.get('reference').button.disabled=!available;if(available)show('reference');else if(current==='reference')show('results')};
  new MutationObserver(syncReference).observe($('referencePanel'),{attributes:true,attributeFilter:['hidden']});
  document.addEventListener('click',event=>{if(event.target.closest('#jumpToReference')){show('reference',true)}},true);
  // The remaining main nodes include the library drawer; keep it outside the split panes.
  const library=$('imageLibraryWide');if(library)document.body.append(library);
  preview?.remove();document.querySelector('.studio-heading')?.remove();document.querySelector('.columns')?.remove();
  candidates=[...$('results').children];setDisplay('gallery');syncReference();
 }else{
  const panels=[...main.children].filter(n=>n.matches('section.panel'));
  const source=kind==='sprite'?main.querySelector('.source-panel'):panels[0],options=kind==='sprite'?source?.nextElementSibling:panels[1];
  if(!source||!options)return;
  const generate=$('generate'),status=$('status');
  footer.append(generate);if(kind==='sprite'){footer.append($('message'));settings.append(status)}else footer.append(status);
  settings.append(source,options);
  if(kind==='sprite'){
   const entry=$('assetEntry'),assetContext=$('assetContext');
   if(entry){settings.prepend(entry);if(assetContext)settings.prepend(assetContext);const syncEntry=()=>{source.hidden=options.hidden=footer.hidden=!entry.hidden};new MutationObserver(syncEntry).observe(entry,{attributes:true,attributeFilter:['hidden']});syncEntry()}
   const examples=$('spriteExamples')?page('examples','동작 예시'):null;
   if(examples)examples.append($('spriteExamples'));
   window.spriteWorkspace={show,mobileView};
   const original=page('source','내 입력 이미지'),result=page('result','내 생성 결과'),image=node('img','creation-source-image'),placeholder=empty('이미지에서 동작을 만들어 보세요','왼쪽에서 이미지를 넣고 동작을 선택하세요. 생성한 영상과 시트는 여기에서 확인합니다.');
   image.alt='동작을 만들 입력 이미지';image.hidden=true;original.append(placeholder,image);result.append($('result'));
   const updateSource=()=>{const img=$('drop').querySelector('img');image.hidden=!img;placeholder.hidden=!!img;if(img&&image.src!==img.src){image.src=img.src;if(current!=='examples')show('source')}};
   new MutationObserver(updateSource).observe($('drop'),{childList:true,subtree:true,attributes:true,attributeFilter:['src']});updateSource();
   const updateResult=()=>{const available=getComputedStyle($('result')).display!=='none';pages.get('result').button.disabled=!available;if(available)show('result',true);else if(current==='result')show('source')};
   new MutationObserver(updateResult).observe($('result'),{attributes:true,attributeFilter:['style','hidden']});updateResult();show(examples?'examples':'source');
  }else{
   const mask=page('mask','눈 · 입 마스킹'),pose=page('pose','관절점'),result=page('result','생성 결과'),placeholder=empty('눈과 입을 지정할 작업 공간','왼쪽에서 이미지를 선택하면 여기에 크게 표시됩니다. 마스킹 후 리깅 초안을 생성하세요.');
   mask.append(placeholder,$('maskPane'));pose.append($('posePane'));result.append($('result'));
   const maskTools=$('maskWork').querySelector('aside.tools'),detail=node('details','creation-mask-settings'),summary=node('summary','','눈 · 입 도구와 단축키');detail.open=true;detail.append(summary,$('maskWork').querySelector('.mode-picker'),$('maskIntro'),maskTools);settings.insertBefore(detail,options);
   const sync=target=>{const hasMask=!$('maskPane').hidden,hasPose=!$('posePane').hidden,hasResult=!$('result').hidden;placeholder.hidden=hasMask;detail.hidden=!hasMask;pages.get('pose').button.disabled=!hasPose;pages.get('result').button.disabled=!hasResult;
    if(target==='result'&&hasResult)show('result',true);else if(target==='maskPane'&&hasMask)show('mask',true);else if(current==='result'&&!hasResult)show('mask');else if(current==='pose'&&!hasPose)show('mask')};
   for(const id of ['maskPane','posePane','result'])new MutationObserver(()=>sync(id)).observe($(id),{attributes:true,attributeFilter:['hidden']});sync();show('mask');
   $('guideOpen').addEventListener('click',()=>show('mask',true));
   const region=node('select','creation-region');region.setAttribute('aria-label','마스킹할 부위');
   for(const [value,label] of [['eyeLeft','왼쪽 눈'],['eyeRight','오른쪽 눈'],['eyebrowLeft','왼쪽 눈썹'],['eyebrowRight','오른쪽 눈썹'],['mouth','입']])region.add(new Option(label,value));
   region.onchange=()=>document.querySelector(`[data-tool="${region.value}"]`)?.click();tools.append(region);
   const syncRegion=()=>{for(const option of region.options){const b=document.querySelector(`[data-tool="${option.value}"]`);option.disabled=b.disabled;if(b.getAttribute('aria-pressed')==='true')region.value=option.value}};
   new MutationObserver(syncRegion).observe(maskTools,{attributes:true,subtree:true,attributeFilter:['aria-pressed','disabled']});syncRegion();
  }
  // Long output descriptions stay available without taking the entire settings column.
  for(const help of options.querySelectorAll(':scope > .help')){const detail=node('details','creation-help'),summary=node('summary','','출력과 사용 안내');help.before(detail);detail.append(summary,help)}
 }
 context();
 const liveMessage=node('p','creation-work-message');liveMessage.setAttribute('aria-hidden','true');output.insertBefore(liveMessage,work);
 const status=kind==='sprite'?$('message'):$('status');if(status){const mirror=()=>{liveMessage.textContent=status.textContent};new MutationObserver(mirror).observe(status,{childList:true,subtree:true,characterData:true});mirror()}
 const queueNote=node('p','creation-queue-note','등록한 작업은 페이지를 닫아도 계속됩니다. 결과는 내 작업과 팀 갤러리에도 저장됩니다.');footer.append(queueNote);
 main.replaceChildren(toolbar,layout);mobileView('settings');
 matchMedia('(max-width:700px)').addEventListener('change',event=>{if(event.matches)mobileView('settings')});
 document.body.dataset.creationWorkspace='ready';
})();
