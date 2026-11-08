/* Nine cards per page. Search/filter state stays local to each library. */
window.createImageLibraryPager=(container,id)=>{
 let items=[],page=1;
 const bars=[document.createElement('nav'),document.createElement('nav')];
 bars.forEach((bar,i)=>{bar.className='library-pagination';bar.id=id+(i?'Bottom':'');bar.setAttribute('aria-label','라이브러리 페이지 '+(i?'아래':'위'))});
 container.before(bars[0]);container.after(bars[1]);
 function render(){
  const pages=Math.max(1,Math.ceil(items.length/9));page=Math.min(Math.max(1,page),pages);
  const active=new Set(items.slice((page-1)*9,page*9));
  for(const card of container.children)card.hidden=!active.has(card);
  for(const bar of bars){
   bar.replaceChildren();
   function button(label,target,disabled=false){const b=document.createElement('button');b.type='button';b.className='ui-btn ui-btn--sm';b.textContent=label;b.disabled=disabled;b.onclick=()=>{page=target;render();bars[0].scrollIntoView({block:'nearest'})};bar.append(b);return b}
   button('이전',page-1,page===1);
   for(let n=1;n<=pages;n++){const b=button(String(n),n);b.setAttribute('aria-label',n+'페이지');if(page===n)b.setAttribute('aria-current','page')}
   button('다음',page+1,page===pages);
   const status=document.createElement('span');status.className='muted';status.setAttribute('role','status');status.textContent=items.length?`${page} / ${pages}페이지 · ${items.length}개 중 ${(page-1)*9+1}–${Math.min(page*9,items.length)}개`:'검색 결과가 없습니다.';bar.append(status);
  }
 }
 return {setItems(next,reset=false){items=next;if(reset)page=1;render()}};
};
