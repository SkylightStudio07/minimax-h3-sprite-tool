/* Optional right-hand library with explicit close and Escape support. */
(()=>{
 const wide=document.getElementById('imageLibraryWide'),toggle=document.getElementById('libraryToggle');
 const buttons=[...document.querySelectorAll('[data-library]')];let returnFocus=toggle;
 function expanded(id){for(const [button,panel] of [['chooseModel','baseGallery'],['browseStyles','styleGallery'],['chooseLook','lookGallery']])document.getElementById(button)?.setAttribute('aria-expanded',String(id===panel))}
 function close(){wide.hidden=true;document.body.classList.remove('library-is-open');toggle.setAttribute('aria-expanded','false');expanded(null);if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true})}
 window.openImageLibrary=id=>{
  if(!buttons.some(b=>b.dataset.library===id))return;
  if(wide.hidden)returnFocus=document.activeElement;
  for(const b of buttons){const active=b.dataset.library===id;b.setAttribute('aria-pressed',String(active));document.getElementById(b.dataset.library).hidden=!active}
  wide.hidden=false;document.body.classList.add('library-is-open');toggle.setAttribute('aria-expanded','true');expanded(id);wide.scrollTop=0;window.dispatchEvent(new CustomEvent('image-library-open',{detail:id}));
 };
 window.closeImageLibrary=close;
 for(const b of buttons)b.onclick=()=>window.openImageLibrary(b.dataset.library);
 toggle.onclick=()=>wide.hidden?window.openImageLibrary('baseGallery'):close();
 document.getElementById('libraryClose').onclick=close;
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!wide.hidden&&!document.querySelector('dialog[open]')){e.preventDefault();close()}});
})();
