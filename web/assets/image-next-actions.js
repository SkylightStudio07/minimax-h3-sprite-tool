/* Decorate the original action buttons; their handlers keep the source image. */
(()=>{
 const css=document.createElement('link');css.rel='stylesheet';css.href='/assets/image-next-actions.css';document.head.append(css);
 const paths={
  sprite:'M9 5l10 7-10 7V5z M4 5v14',
  rig:'M8 10h.01 M16 10h.01 M8 15c2 2 6 2 8 0 M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  face:'M9 3H5a2 2 0 0 0-2 2v4 M15 3h4a2 2 0 0 1 2 2v4 M21 15v4a2 2 0 0 1-2 2h-4 M9 21H5a2 2 0 0 1-2-2v-4 M12 7l1.5 3.5L17 12l-3.5 1.5L12 17l-1.5-3.5L7 12l3.5-1.5L12 7z'
 };
 const descriptions={sprite:'걷기·공격 등 동작을 이어서 만들어요',rig:'눈·입과 레이어를 나누어 움직여요',face:'얼굴만 다듬고 원본은 그대로 보관해요'};
 window.createImageNextActions=entries=>{
  const section=document.createElement('section');section.className='image-next-actions';section.setAttribute('aria-label','이 이미지로 계속하기');
  const heading=document.createElement('h3');heading.textContent='이 이미지로 계속하기';
  const grid=document.createElement('div');grid.className='image-next-grid';grid.style.setProperty('--next-count',entries.length);
  for(const {kind,button} of entries){
   const label=button.textContent;button.setAttribute('aria-label',label);button.className='image-next-action';button.dataset.nextAction=kind;
   const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');
   const path=document.createElementNS(icon.namespaceURI,'path');path.setAttribute('d',paths[kind]);icon.append(path);
   const text=document.createElement('span'),name=document.createElement('strong'),description=document.createElement('small');name.textContent=label;description.textContent=descriptions[kind];text.append(name,description);
   const arrow=document.createElement('span');arrow.className='image-next-arrow';arrow.textContent='→';arrow.setAttribute('aria-hidden','true');button.replaceChildren(icon,text,arrow);grid.append(button);
  }
  section.append(heading,grid);return section;
 };
})();
