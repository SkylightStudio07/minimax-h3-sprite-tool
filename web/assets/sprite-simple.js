/* Action and output pickers. The original form controls stay the source of truth,
 * so presets, examples and "recreate" keep working by setting them directly. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 if(!$('spriteActionPicker'))return;
 const figure={
  idle:'<circle cx="16" cy="6" r="3.5"/><path d="M16 10v10M16 13l-5 6M16 13l5 6M16 20l-4 9M16 20l4 9"/>',
  walk:'<circle cx="17" cy="6" r="3.5"/><path d="M16 10l-1 10M16 13l-6 4M16 13l5 6M15 20l-5 9M15 20l6 9"/>',
  run:'<circle cx="20" cy="6" r="3.5"/><path d="M18 10l-5 9M17 13l-7-1M17 13l6 5M13 19l-7 3M13 19l7 4-2 6"/>',
  attack:'<circle cx="12" cy="7" r="3.5"/><path d="M12 11v9M12 14l7-2M12 14l-5 5M12 20l-5 9M12 20l5 9M19 12L29 3"/>',
  cast:'<circle cx="13" cy="7" r="3.5"/><path d="M13 11v9M13 14l8-3M13 14l-5 5M13 20l-4 9M13 20l4 9"/><circle cx="26" cy="9" r="3"/>',
  hit:'<circle cx="9" cy="8" r="3.5"/><path d="M12 11l3 9M13 14l-7 3M13 14l6-4M15 20l-5 9M15 20l5 9M24 7l5-3M25 12h5M24 17l5 3"/>',
  death:'<circle cx="6" cy="22" r="3.5"/><path d="M10 23h11M14 23l3-5M14 23l4 4M21 23l8-3M21 23l8 4"/>',
  jump:'<circle cx="16" cy="5" r="3.5"/><path d="M16 9v9M16 12l-7-4M16 12l7-4M16 18l-5 4 1 5M16 18l5 4-1 5"/>',
  custom:'<path d="M6 26l1-6L21 6l5 5-14 14zM18 9l5 5"/>'
 };
 const actions=[...$('action').options],effectActions=['attack','cast'];
 const fire=(node,...types)=>types.forEach(type=>node.dispatchEvent(new Event(type,{bubbles:true})));
 const picker=$('spriteActionPicker'),kinds=[...$('spriteOutputKind').querySelectorAll('button')];
 for(const option of actions){
  const button=document.createElement('button');button.type='button';button.dataset.action=option.value;
  button.innerHTML=`<svg viewBox="0 0 32 32" aria-hidden="true">${figure[option.value]}</svg>`;button.append(option.textContent);
  button.onclick=()=>choose(option.value);picker.append(button);
 }
 function sync(){
  const action=$('action').value,effect=$('combatEffect').value!=='none';
  for(const button of picker.children)button.setAttribute('aria-pressed',String(button.dataset.action===action));
  for(const button of kinds)button.setAttribute('aria-pressed',String((button.dataset.kind==='pixel')===$('pixelOutput').checked));
  $('spriteCombat').hidden=!(effect||effectActions.includes(action));
 }
 function choose(action){
  if($('action').value===action)return;
  $('action').value=action;fire($('action'),'change','input');
  if(!effectActions.includes(action)&&$('combatEffect').value!=='none'){$('combatEffect').value='none';fire($('combatEffect'),'change')}
  sync();
 }
 for(const button of kinds)button.onclick=()=>{
  const pixel=button.dataset.kind==='pixel';if($('pixelOutput').checked===pixel)return;
  $('pixelOutput').checked=pixel;fire($('pixelOutput'),'change','input');updateResolution();sync();
 };
 $('combatEffect').addEventListener('change',sync);
 for(const id of ['applySetting','applyChibiCombat'])$(id).addEventListener('click',sync);
 const recreate=window.applyRecreatePreset;
 window.applyRecreatePreset=s=>{const result=recreate(s);sync();return result};
 $('spriteMakeArt').onclick=event=>{if(parent===window)return;event.preventDefault();parent.location.hash='#/create/image';parent.renderRoute?.()};
 sync();
})();
