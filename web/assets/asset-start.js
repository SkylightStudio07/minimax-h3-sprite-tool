/* Game view for the motion studio. Nothing is sent unless a view is chosen or
 * restored, so by default the prompt follows the input image alone. */
(()=>{
 const el=id=>document.getElementById(id),view=el('assetView'),facing=el('facing');
 if(!view)return;
 const directions=['front','front-right','right','back-right','back','back-left','left','front-left'];
 const fallback={side:'right',topdown:'front',isometric:'front-right'};
 const implicit={type:'side',directionCount:1,facing:'right'};
 let saved=null;
 function spec(){
  const type=view.value;if(!type)return null;
  const kept=saved?.type===type?saved:null;
  return {type,directionCount:kept?.directionCount||1,facing:directions.includes(facing.value)?facing.value:kept?.facing||fallback[type]};
 }
 const current=()=>spec()||implicit;
 const notify=()=>window.dispatchEvent(new CustomEvent('asset-type-change',{detail:current()}));
 function restore(value){
  const known=value&&fallback[value.type]&&directions.includes(value.facing);
  saved=known?{type:value.type,directionCount:[1,4,8].includes(value.directionCount)?value.directionCount:1,facing:value.facing}:null;
  view.value=saved?.type||'';
  if(value)facing.value=saved&&['front','right','left','back'].includes(saved.facing)?saved.facing:'preserve';
  notify();
 }
 view.addEventListener('change',()=>{saved=null;if(view.value&&facing.value==='preserve')facing.value=fallback[view.value];notify()});
 window.assetStart={payload(){const value=spec();return value?{assetSpec:value}:{}},current,restore};
 const receive=window.receiveGeneratedImage;
 if(receive)window.receiveGeneratedImage=async(file,s)=>{const result=await receive(file);restore(s);return result};
 const recreate=window.applyRecreatePreset;
 if(recreate)window.applyRecreatePreset=s=>{const result=recreate(s);restore(s.assetSpec);return result};
})();
