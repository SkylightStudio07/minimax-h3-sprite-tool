// Isolated browser regression; no GPU or production mutations.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVR4nGPcYmT0nwEPYMInOXwUAAArdAIn9t4S0wAAAABJRU5ErkJggg==','base64');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];let saved=null,requests=[],polls=0;
  page.on('pageerror',error=>errors.push(error.message));
  const layers=[{id:'mouth_open',key:'expression:mouth_open',kind:'expression',runtimeName:'mouth_open',left:40,top:40,width:8,height:8,defaultVisible:false,asset:'/fixture.png',originalAsset:'/fixture.png'},
   {id:'objects',key:'part:objects',kind:'part',runtimeName:'objects',left:10,top:10,width:8,height:8,defaultVisible:true,asset:'/fixture.png',originalAsset:'/fixture.png'}];
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url()),file=url.pathname;
   if(file==='/rigging-editor'||file==='/share/rig/internal/inspector')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'web/rigging-editor.html'))});
   if(file.startsWith('/assets/')||['/rigging-expressions.js','/rigging-bones.js','/rigging-animation.js','/rigging-animation-math.js'].includes(file))return route.fulfill({contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'font/woff2',body:fs.readFileSync(path.join(root,'web',file))});
   if(file==='/fixture.png')return route.fulfill({contentType:'image/png',body:png});
   if(file.endsWith('/regenerate')){requests.push(route.request().postDataJSON());polls=0;return route.fulfill({status:202,json:{taskId:'candidate'}})}
   if(file.endsWith('/regenerate/candidate')){polls++;return route.fulfill({json:polls===1?{state:'queued',message:'대기 중'}:{state:'complete',revision:0,layerKey:requests.at(-1).layerKey,left:38,top:39,width:8,height:8,imageData:'data:image/png;base64,'+png.toString('base64')}})}
   if(file.endsWith('/revisions')){saved=route.request().postDataJSON();return route.fulfill({json:{revision:1}})}
   if(file.endsWith('/rig-edit'))return route.fulfill({json:{canvas:{width:96,height:96},revision:saved?1:0,layers,versions:[]}});
   return route.fulfill({status:404});
  });
  await page.goto('http://sprite.test/rigging-editor?job=test');await page.waitForFunction(()=>model&&parts.length===2);
  assert.equal(await page.locator('#regenerateTarget option').count(),2);
  await page.locator('#regenerateTarget').selectOption('expression:mouth_open');
  await page.locator('#regenerateHint').fill('작게 벌린 입');await page.locator('#regeneratePart').click();
  await page.locator('dialog.rig-candidate-dialog').waitFor({state:'visible'});
  assert.equal(requests[0].hint,'작게 벌린 입');
  await page.locator('#dismissCandidate').click();assert.equal(await page.evaluate(()=>history.length),0);
  await page.evaluate(()=>candidateDialog.showModal());await page.locator('#acceptCandidate').click();
  assert.equal(await page.evaluate(()=>history.at(-1).kind),'layer_png');assert.equal(await page.evaluate(()=>selected.left),38);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>selected.left),40);
  await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>selected.left),38);
  // Drawing and rebuilding after replacement must retain the candidate geometry.
  await page.evaluate(()=>{history.push({kind:'erase',layerKey:selected.key,size:4,points:[{x:41,y:42,p:1}]});rebuild(selected.key)});
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>selected.left),38);
  await page.locator('#save').click();await page.waitForFunction(()=>model.revision===1);
  assert.deepEqual(saved.operations.map(op=>op.kind),['layer_png']);assert.equal(saved.operations[0].left,38);assert(!JSON.stringify(saved).includes('localCanvas'));
  await page.locator('#regenerateTarget').selectOption('part:objects');assert.equal(await page.locator('#regenerateHint').isDisabled(),true);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(root,'outputs/rigging-regenerate-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  // Internal shared editors use their capability route, without requiring an owner login.
  saved=null;await page.goto('http://sprite.test/share/rig/internal/inspector');await page.waitForFunction(()=>model&&parts.length===2);
  assert.equal(await page.evaluate(()=>regenerationEndpoint()),'/share/rig/internal/rig-edit/regenerate');
  console.log('Regeneration browser passed: target, queue, compare, cancel, apply, draw, undo/redo, save, mobile, share.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
