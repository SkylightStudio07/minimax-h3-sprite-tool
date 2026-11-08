/* Disposable accounts, real HTTP, optional real local caption + GPU generation.
 * --real-image writes evidence to outputs; it never queues production jobs. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),real=process.argv.includes('--real-image');
const shot=name=>path.join(root,'outputs',`image-journey-${real?'real':'fixture'}-${name}.png`);
(async()=>{
 const fixture=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tools/serve_character_fixture.py',...(real?['--real-image']:[])],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let stderr='',browser,info;fixture.stderr.on('data',b=>stderr+=b);
 try{
  info=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Fixture startup: '+stderr)),20000);fixture.stdout.on('data',b=>{out+=b;for(const line of out.trim().split('\n'))try{const d=JSON.parse(line);if(d.port){clearTimeout(timer);resolve(d);return}}catch{}});fixture.on('exit',()=>{clearTimeout(timer);reject(Error(stderr))})});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],base='http://127.0.0.1:'+info.port;
  page.on('pageerror',e=>errors.push(e.message));
  assert.equal((await page.request.post(base+'/api/login',{data:{username:'fixture',password:'fixture-password'},headers:{'X-Sprite-Request':'1'}})).status(),200);
  const state=await (await page.request.get(base+'/api/images/models')).json();
  let captured,caption;
  page.on('request',r=>{if(r.url().endsWith('/api/images/generate'))captured=r.postDataJSON()});
  page.on('response',async r=>{if(r.url().endsWith('/api/images/describe')&&r.ok())caption=await r.json()});
  if(!real){
   await page.route('**/api/images/models',r=>r.fulfill({json:{...state,comfy:true,caption:{ready:true,external:false},models:state.models.map(m=>({...m,ready:true})),styles:state.styles.map(s=>({...s,installed:true}))}}));
   await page.route('**/api/images/describe',r=>r.fulfill({json:{prompt:'short purple hair, black hood, navy long coat, black boots',summary:'후드·의상을 확인하세요.',provider:'local'}}));
   await page.route('**/api/images/generate',r=>r.fulfill({status:202,json:{jobId:'a'.repeat(32)}}));
   await page.route('**/api/jobs/'+ 'a'.repeat(32),r=>r.fulfill({json:{id:'a'.repeat(32),state:'complete',jobType:'image',assetSpec:captured.assetSpec,settings:captured,images:[{url:'/api/images/'+ 'a'.repeat(32)+'/image-1.png',seed:42}]}}));
   const image=await page.request.get(base+'/api/images/art/image-1.png');
   await page.route('**/api/images/'+ 'a'.repeat(32)+'/image-1.png',r=>r.fulfill({contentType:'image/png',body:Buffer.from(imageBody)}));
   var imageBody=await image.body();
  }
  await page.goto(base+'/#/create/image');const f=page.frameLocator('#imageStudio');
  await f.locator('#model option[value="wai-cutscene-counter"]').waitFor({state:'attached'});
  await f.locator('#styleId option[value="epic-seven-sprites"]').waitFor({state:'attached'});
  await f.locator('[data-task="convert"]').click();
  assert(await f.locator('#referenceSetup').isVisible());
  assert(await f.locator('#referenceSetup #file').isVisible());
  assert(!(await f.locator('#promptExamples').isVisible()));
  if(real)await f.locator('#file').setInputFiles(path.join(root,'outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png'));
  else await f.locator('#file').setInputFiles({name:'reference.png',mimeType:'image/png',buffer:imageBody});
  await page.screenshot({path:shot('reference'),fullPage:true});
  await f.locator('#describeReference').waitFor({state:'visible'});await f.locator('#describeReference').click();
  console.log('Reading reference appearance'+(real?' (real Qwen-VL CPU)':' (fixture)'));
  await f.locator('#captionReview').waitFor({state:'visible',timeout:260000});
  assert.equal(await f.locator('#prompt').inputValue(),'','Analysis must not silently replace user text');
  await f.locator('#captionReplace').click();const appearance=await f.locator('#prompt').inputValue();assert(appearance.length>=20);
  await f.locator('#prompt').fill(appearance+', full body, side view, facing right, battle ready stance, plain grey background');
  await f.locator('#browseStyles').click();await f.locator('#styleSearch').fill('epic-seven-sprites');await f.locator('[data-use-style="epic-seven-sprites"]').click();
  assert.equal(await f.locator('#model').inputValue(),'flanime-xl');
  assert((await f.locator('#prompt').inputValue()).startsWith(appearance));
  assert.equal(await f.locator('#poseEnabled').isChecked(),true);
  await f.locator('#count').selectOption('1');
  await f.locator('#background').selectOption('keep');
  await f.locator('#advancedSettings > summary').click();await f.locator('#size').selectOption('1024x1536');await f.locator('#steps').fill('32');await f.locator('#advancedSettings > summary').click();
  // Upload and analysis come before the appearance field on both PC and mobile.
  await page.setViewportSize({width:390,height:844});
  assert(await f.locator('#referenceSetup').evaluate((e)=>Boolean(e.compareDocumentPosition(document.getElementById('prompt'))&Node.DOCUMENT_POSITION_FOLLOWING)));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:shot('mobile'),fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await f.locator('#generate').click();console.log('Generating reference + additional style'+(real?' (real GPU)':' (fixture)'));
  await f.locator('#results img').first().waitFor({state:'visible',timeout:240000});
  assert(captured.imageData);assert.equal(captured.styleId,'epic-seven-sprites');assert.equal(captured.assetSpec.facing,'right');assert(captured.pose);
  await page.screenshot({path:shot('result'),fullPage:true});
  // The completed result keeps its direction even if the form changes afterward.
  await f.locator('#assetFacing').selectOption('left');
  await f.locator('#results button').filter({hasText:'동작 만들기'}).first().click();
  await page.waitForURL('**/#/create/sprite');const motion=page.frameLocator('#studio');
  await motion.locator('#drop img').waitFor();assert.equal(await motion.locator('#facing').inputValue(),'right');
  assert.equal(await motion.locator('#assetEntry').isVisible(),false);
  assert((await motion.locator('#resolution').textContent()).includes(real?'1024×1536':'32×64'));
  const loadedMotion=await motion.locator('#drop img').getAttribute('src');
  // A corrupt replacement must not erase the successfully loaded character.
  const motionFrame=page.frames().find(t=>new URL(t.url()).pathname==='/studio');
  const invalid=await motionFrame.evaluate(async()=>{try{await window.receiveGeneratedImage(new File(['broken'],'broken.png',{type:'image/png'}));return false}catch{return true}});
  assert(invalid);assert.equal(await motion.locator('#drop img').getAttribute('src'),loadedMotion);
  await page.screenshot({path:shot('motion'),fullPage:true});
  await page.locator('[data-route="create/image"]').click();await f.locator('#results img').first().waitFor();
  await f.locator('#results button').filter({hasText:'Live2D 만들기'}).first().click();
  await page.waitForURL('**/#/create/rig');const rig=page.frameLocator('#riggingStudio');
  await rig.locator('#maskPane').waitFor({state:'visible'});assert(await rig.locator('#sourcePreview').isVisible());
  assert.equal(await rig.locator('#imageCanvas').getAttribute('width'),real?'1024':'32');
  await page.screenshot({path:shot('live2d'),fullPage:true});
  assert.deepEqual(errors,[]);
  if(real)fs.writeFileSync(path.join(info.imageRoot,'journey.json'),JSON.stringify({caption,request:{...captured,imageData:'[omitted]'},motionDirection:'right',live2dSourceSize:[1024,1536],errors},null,2));
  console.log('PASS: reference upload → review caption → compatible style → generate → motion direction + image → Live2D mask canvas. '+(real?info.imageRoot:''));
 }finally{if(browser)await browser.close();fixture.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
