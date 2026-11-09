/* Isolated profile UI checks; no production accounts or GPU execution. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage(),errors=[];let submitted;
  const status={spriteBackground:{ready:true},comfy:true,modelsReady:true,licenseConfirmed:true,spriteWorkflows:[{id:'standard',ready:true},{id:'fasth3-sprite',ready:false}]};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://sprite.test/**',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname==='/studio')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8')});
   if(u.pathname.startsWith('/assets/'))return route.fulfill({path:path.join(__dirname,'../web',u.pathname)});
   if(u.pathname==='/api/status')return route.fulfill({json:status});
   if(u.pathname==='/api/generate'){submitted=route.request().postDataJSON();return route.fulfill({json:{jobId:'test'}})}
   if(u.pathname==='/api/jobs/test')return route.fulfill({json:{state:'cancelled'}});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sprite.test/studio');
  assert.equal(await page.locator('#assetEntry').count(),0,'Images go in without a type gate');
  await page.locator('#spriteAdvanced').evaluate(d=>{d.open=true});
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('준비 완료'));
  assert(await page.locator('#workflowId option[value="fasth3-sprite"]').isDisabled());
  await page.locator('#settingCollection').selectOption('walk_video');await page.locator('#applySetting').click();assert((await page.locator('#message').textContent()).includes('준비되지'));assert.equal(await page.locator('#workflowId').inputValue(),'standard');
  page.on('dialog',dialog=>dialog.accept());
  status.spriteWorkflows[1].ready=true;await page.evaluate(()=>check());
  await page.locator('#applySetting').click();assert.equal(await page.locator('#action').inputValue(),'walk');assert((await page.locator('#prompt').inputValue()).includes('one support foot'));
  await page.locator('#settingCollection').selectOption('run_video');await page.locator('#applySetting').click();assert.equal(await page.locator('#action').inputValue(),'run');assert((await page.locator('#prompt').inputValue()).includes('airborne phase'));
  assert.equal(await page.locator('#motionStrength').inputValue(),'high');assert.equal(await page.locator('#duration').inputValue(),'3');assert.equal(await page.locator('#frames').inputValue(),'12');assert.equal(await page.locator('#facing').inputValue(),'right');assert.equal(await page.locator('#stabilize').isChecked(),false);assert.equal(await page.locator('#optimizeLoop').isChecked(),false);
  assert(await page.locator('#size').isDisabled());assert(await page.locator('#negativeEnabled').isDisabled());
  assert(await page.locator('#samplingMode').isHidden());
  assert.deepEqual(await page.evaluate(()=>calculatedSize()),[512,512]);
  await page.locator('#file').setInputFiles({name:'test.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
  assert.equal(await page.locator('#removeBackground').isChecked(),true);
  assert.equal(await page.locator('#backgroundRemoval').inputValue(),'ai');
  await page.locator('#backgroundRemoval').selectOption('flat');
  assert(await page.locator('#backgroundTolerance').isVisible());
  await page.locator('#backgroundRemoval').selectOption('ai');
  assert(await page.locator('#backgroundTolerance').isHidden());
  await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('취소'));
  assert.equal(submitted.removeBackground,true);assert.equal(submitted.backgroundRemoval,'ai');
  assert.equal(submitted.assetSpec,undefined,'No game view is sent unless chosen');
  assert.equal(submitted.animationType,'run');assert.equal(submitted.frameCount,12);assert.equal(submitted.motionStrength,'high');assert.equal(submitted.stabilize,false);assert.equal(submitted.optimizeLoop,false);assert(submitted.prompt.includes('airborne phase'));
  assert.equal(submitted.workflowId,'fasth3-sprite');assert.equal(submitted.width,512);assert.equal(submitted.height,512);assert.equal(submitted.negativeEnabled,false);
  await page.locator('#workflowId').selectOption('standard');assert(await page.locator('#samplingMode').isVisible());assert(await page.locator('#size').isEnabled());
  await page.evaluate(()=>window.applyRecreatePreset({workflowId:'fasth3-sprite',width:512,height:512}));
  assert.equal(await page.locator('#workflowId').inputValue(),'fasth3-sprite');assert(await page.locator('#samplingMode').isHidden());
  assert.deepEqual(errors,[]);console.log('PASS: workflow installation gate, fixed settings, submission, restore, legacy controls');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
