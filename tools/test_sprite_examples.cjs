/* Run the actual form, workspace and example scripts in JSDOM. No rendering claim. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,ResourceLoader,VirtualConsole}=require(process.env.SPRITE_TEST_JSDOM||'jsdom');
const root=path.resolve(__dirname,'..'),catalog=JSON.parse(fs.readFileSync(path.join(root,'web/assets/sprite-examples/catalog.json'),'utf8'));
class Assets extends ResourceLoader{fetch(url){const u=new URL(url);if(u.pathname.endsWith('.js'))return Promise.resolve(fs.readFileSync(path.join(root,'web',u.pathname)));return null}}
const errors=[],requests=[],consoleBridge=new VirtualConsole();consoleBridge.on('jsdomError',error=>errors.push(error.message));
const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:'https://sprite.test/studio',runScripts:'dangerously',resources:new Assets(),pretendToBeVisual:true,virtualConsole:consoleBridge,beforeParse(w){
 w.matchMedia=q=>({matches:q.includes('prefers-reduced-motion'),addEventListener(){},removeEventListener(){}});w.ResizeObserver=class{observe(){}};w.HTMLElement.prototype.scrollIntoView=function(){};w.setInterval=()=>0;
 w.confirm=()=>true;w.fetch=async(url,init)=>{requests.push({url,method:init?.method||'GET'});assert(!init?.method||init.method==='GET','Example browsing must not submit work');
  if(url==='/api/status')return {json:async()=>({comfy:true,modelsReady:true,licenseConfirmed:true,spriteBackground:{ready:true},spriteWorkflows:[{id:'standard',ready:true},{id:'fasth3-sprite',ready:true}]})};
  if(url==='/api/characters')return {ok:true,json:async()=>({characters:[]})};
  if(url==='assets/sprite-examples/catalog.json')return {ok:true,json:async()=>catalog};
  throw Error('Unexpected request '+url);
 };
}});
const tick=()=>new Promise(r=>setTimeout(r,20));
(async()=>{
 await new Promise(resolve=>dom.window.addEventListener('load',resolve));await tick();
 const w=dom.window,d=w.document,$=id=>d.getElementById(id);
 assert.deepEqual(errors,[]);assert.equal(d.body.dataset.creationWorkspace,'ready');
 assert.equal($('assetEntry'),null,'Images go in without a type gate');
 const pickView=value=>{$('assetView').value=value;$('assetView').dispatchEvent(new w.Event('change',{bubbles:true}))};
 assert.equal($('spriteExampleDetail').hidden,false);assert.equal($('spriteExampleCards').hidden,false);assert.equal($('spriteTypeGuide').hidden,true);assert.equal(Object.keys(w.assetStart.payload()).length,0,'No game view is sent unless chosen');
 for(const type of ['topdown','isometric']){
  pickView(type);
  assert.equal($('spriteExampleDetail').hidden,true);assert.equal($('spriteExampleCards').hidden,true);assert.equal($('applyChibiCombat').hidden,true);assert.equal($('spriteTypeGuide').hidden,false);
  assert.equal($('spriteExampleHero').hasAttribute('src'),false);assert(!$('spriteTypeGuide').textContent.includes('푸른 검기'));assert.equal(w.assetStart.payload().assetSpec.type,type);
  const action=$('action').value;$('spriteExampleApply').click();assert.equal($('action').value,action,'Mismatched sample must not apply');
  $('facing').value='preserve';
 }
 pickView('');assert.equal($('spriteExampleDetail').hidden,false);assert.equal($('spriteExampleCards').hidden,false);assert.equal($('spriteTypeGuide').hidden,true);
 assert.equal($('spriteExampleCards').children.length,catalog.examples.length);assert.equal($('spriteExampleLoading').hidden,true);
 assert.equal($('spriteExamples').closest('[data-page]').dataset.page,'examples');assert.equal($('spriteExamples').closest('[data-page]').hidden,false);
 assert.equal($('spriteExampleHero').getAttribute('src'),catalog.examples.find(x=>x.id==='pixel-energy').poster,'Reduced motion must use a still');
 assert.equal(d.querySelectorAll('[data-sprite-filter]').length,3);assert.equal($('spriteExamples').dataset.category,'pixel');
 assert.equal([...$('spriteExampleCards').children].filter(x=>!x.hidden).length,4);
 assert([...$('spriteExampleCards').children].filter(x=>!x.hidden).every(x=>x.dataset.example.startsWith('pixel-')));
 const chibiExamples=catalog.examples.filter(x=>x.category==='chibi');
 d.querySelector('[data-sprite-filter="chibi"]').click();
 if(chibiExamples.length){
  assert.equal($('spriteExampleDetail').hidden,false);assert.equal($('spriteExampleCards').hidden,false);assert.equal($('spriteCategoryEmpty').hidden,true);
  assert.equal([...$('spriteExampleCards').children].filter(x=>!x.hidden).length,chibiExamples.length);
  assert([...$('spriteExampleCards').children].filter(x=>!x.hidden).every(x=>x.dataset.example.startsWith('chibi-')));
 }else{
  assert.equal($('spriteExampleDetail').hidden,true);assert.equal($('spriteExampleCards').hidden,true);assert.equal($('spriteCategoryEmpty').hidden,false);assert.equal($('spriteExampleHero').hasAttribute('src'),false);
  const unchanged=$('action').value;$('spriteExampleApply').click();assert.equal($('action').value,unchanged);
 }
 d.querySelector('[data-sprite-filter="pixel"]').click();assert.equal($('spriteCategoryEmpty').hidden,true);assert.equal($('spriteExampleDetail').hidden,false);

 $('spriteExampleSheet').click();assert($('spriteExampleHero').src.endsWith('pixel-energy-sheet.webp'));
 $('spriteExampleMotion').click();$('spriteExamplePlayback').click();assert($('spriteExampleHero').src.endsWith('pixel-energy.webp'));
 $('spriteExampleBackground').value='light';$('spriteExampleBackground').dispatchEvent(new w.Event('change'));assert.equal($('spriteExamples').dataset.background,'light');
 d.querySelector('[data-sprite-filter="normal"]').click();assert.equal([...$('spriteExampleCards').children].filter(x=>!x.hidden).length,catalog.examples.filter(x=>x.category==='normal').length);assert.equal($('spriteExampleTitle').textContent,'일반 · 대기');const normalSample=catalog.examples.find(x=>x.id==='normal-run')||catalog.examples.find(x=>x.id==='normal-walk')||catalog.examples.find(x=>x.id==='normal-idle');d.querySelector(`[data-example="${normalSample.id}"]`).click();
 const input=d.createElement('img');input.src='https://sprite.test/my-character.png';$('drop').append(input);await tick();
 $('spriteExampleApply').click();await tick();assert.equal($('action').value,normalSample.recipe.animationType);assert.equal($('workflowId').value,normalSample.recipe.workflowId);assert.equal($('size').value,`${normalSample.recipe.width}x${normalSample.recipe.height}`);assert.equal($('prompt').value,normalSample.recipe.prompt);assert.equal($('pixelOutput').checked,false);assert.equal($('drop').querySelector('img'),input);
 d.querySelector('[data-sprite-filter="pixel"]').click();assert.equal([...$('spriteExampleCards').children].filter(x=>!x.hidden).length,4);d.querySelector('[data-example="pixel-energy"]').click();$('spriteExampleApply').click();await tick();
 assert.equal($('action').value,'attack');assert.equal($('combatEffect').value,'blue_slash');assert.equal($('motionSpeed').value,'1');assert.equal($('trimAction').checked,false);assert($('prompt').value.includes('ONE clear sword attack'));assert.equal($('size').value,'768x640');assert.equal($('pixelOutput').checked,true);assert.equal($('drop').querySelector('img'),input);assert.equal($('facing').value,'right');
 d.querySelector('[data-sprite-filter="pixel"]').click();d.querySelector('[data-example="pixel-attack"]').click();$('spriteExampleApply').click();await tick();assert.equal($('combatEffect').value,'none');assert.equal($('pixelOutput').checked,true);
 d.querySelector('[data-example="pixel-idle"]').click();$('spriteExampleApply').click();assert.equal($('action').value,'idle');assert($('prompt').value.includes('chibi'));assert.equal($('facing').value,'preserve');assert.equal($('motionStrength').value,'low');
 assert.equal(w.assetStart.current().type,'side','A pixel example must stay in the side type');
 $('action').dispatchEvent(new w.Event('input'));assert(d.querySelector('.sprite-choice-summary b').textContent.includes('직접 조정'));
 d.querySelector('[data-sprite-filter="normal"]').click();const normalAttack=catalog.examples.find(x=>x.id==='normal-attack')||normalSample;d.querySelector(`[data-example="${normalAttack.id}"]`).click();await w.eval('workflowStates=[]');$('spriteExampleApply').click();assert.equal($('action').value,normalAttack.recipe.animationType);assert.equal($('workflowId').value,'standard');assert.equal($('pixelOutput').checked,false);assert.equal($('prompt').value,normalAttack.recipe.prompt);assert.equal($('loop').checked,normalAttack.recipe.loop);assert.equal($('motionSpeed').value,String(normalAttack.recipe.motionSpeed??1));assert.equal($('trimAction').checked,normalAttack.recipe.trimAction??false);assert.equal($('motionPadding').value,String(normalAttack.recipe.motionPadding));assert.equal($('removeBackground').checked,normalAttack.recipe.removeBackground);assert.equal($('backgroundRemoval').value,normalAttack.recipe.backgroundRemoval);assert.equal($('backgroundRemoval').querySelector('[value="ai"]').disabled,false,'Switching from pixel must release the AI lock');if(normalAttack.recipe.backgroundRemoval==='ai'){const ai=$('backgroundRemoval').querySelector('[value="ai"]');ai.dataset.ready='false';w.spriteCombatControls();assert.equal(ai.disabled,true);$('spriteExampleApply').click();assert($('spriteExampleStatus').textContent.includes('준비'));ai.dataset.ready='true';w.spriteCombatControls();$('spriteExampleApply').click();assert.equal($('backgroundRemoval').value,'ai');}
 for(const item of catalog.examples.filter(x=>x.effect==='subtle'&&x.category==='normal')){
  assert.equal(item.category,'normal');assert.equal(item.recipe.combatEffect,'subtle');
  d.querySelector(`[data-example="${item.id}"]`).click();$('spriteExampleApply').click();await tick();
  assert.equal($('combatEffect').value,'subtle');assert.equal($('effectStrength').value,'low');assert.equal($('effectDescription').value,'');
  assert.equal($('motionPadding').value,'58');assert.equal($('frames').value,'24');assert.equal($('loop').checked,false);assert.equal($('pixelOutput').checked,false);
  assert.equal($('size').value,'768x768');assert.equal($('prompt').value,item.recipe.prompt);assert.equal($('motionSpeed').value,String(item.recipe.motionSpeed));
  assert.equal($('backgroundRemoval').value,'flat');assert.equal($('removeBackground').checked,true);
  assert.equal($('drop').querySelector('img'),input);assert(d.querySelector('a[download]').href.endsWith(item.gif));
  assert($('combatEffectHint').textContent.includes('짧고 옅은'));
 }
 assert.equal(catalog.examples.filter(x=>x.effect==='subtle'&&x.category==='normal').length,2);
 if(chibiExamples.length){
  d.querySelector('[data-sprite-filter="chibi"]').click();assert.equal(chibiExamples.length,2);
  for(const item of chibiExamples){
   assert.equal(item.style,'painted');assert.equal(item.pixelGrid,null);assert.equal(item.characterId,'original-reference-chibi-cartographer-20261023');
   d.querySelector(`[data-example="${item.id}"]`).click();$('spriteExampleApply').click();await tick();
   assert.equal($('pixelOutput').checked,false);assert.equal($('prompt').value,item.recipe.prompt);
   assert.equal($('workflowId').value,'standard');assert.equal($('size').value,'768x768');
   assert.equal($('motionPadding').value,String(item.recipe.motionPadding));assert.equal($('frames').value,String(item.recipe.frameCount));
   assert.equal($('motionSpeed').value,String(item.recipe.motionSpeed));assert.equal($('loop').checked,item.recipe.loop);
   assert.equal($('combatEffect').value,item.recipe.combatEffect);assert.equal($('backgroundRemoval').value,item.recipe.backgroundRemoval);
   assert.equal($('drop').querySelector('img'),input);assert(d.querySelector('a[download]').href.endsWith(item.gif));
   assert(!$('prompt').value.includes('plum-brown'),'Applying a motion must preserve the user character identity');
   if(item.id==='chibi-reference-attack'){
    assert.equal($('backgroundRemoval').value,'ai-sparks');assert.equal($('loop').checked,false);
    assert($('spriteExampleNote').textContent.includes('첫 공격'));
    const ai=$('backgroundRemoval').querySelector('[value="ai"]');ai.dataset.ready='false';
    $('spriteExampleApply').click();assert($('spriteExampleStatus').textContent.includes('준비'));
    ai.dataset.ready='true';$('spriteExampleApply').click();assert.equal($('backgroundRemoval').value,'ai-sparks');
   }
  }
 }

 assert.equal($('drop').querySelector('img'),input);assert(!requests.some(x=>x.method!=='GET'));assert.deepEqual(errors,[]);
 assert.deepEqual([...new Set(catalog.examples.filter(x=>x.category==='pixel').map(x=>x.characterId))],['chibi-anime-swordswoman-20261020']);
 for(const item of catalog.examples)for(const key of ['animation','poster','sheet','source'])assert(fs.existsSync(path.join(root,'web',item[key])),item[key]);
 w.assetStart.restore({type:'topdown',directionCount:4,facing:'front'});assert.equal($('spriteExampleDetail').hidden,true);assert.equal($('spriteExampleCards').hidden,true);assert($('spriteTypeGuide').textContent.includes('탑다운'));
 w.assetStart.restore({type:'side',directionCount:1,facing:'right'});assert.equal($('spriteExampleDetail').hidden,false);
 pickView('isometric');assert.equal($('spriteExampleDetail').hidden,true);assert($('spriteTypeGuide').textContent.includes('아이소메트릭'));
 console.log('PASS game view choice, reviewed real-media examples, workspace default, reduced motion, play/pause, sheet view, background, filters, recipe apply, engine gate, existing input preservation, no generation side effects');
 dom.window.close();
})().catch(error=>{console.error(error);dom.window.close();process.exitCode=1});
