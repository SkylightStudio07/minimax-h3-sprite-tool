/* Full HTTP/gallery/candidate flow. --real-image uses the actual local GPU. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),real=process.argv.includes('--real-image'),source='c'.repeat(32);
(async()=>{
 const fixture=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tools/serve_character_fixture.py','--face-refine',real?'--real-image':'--fake-face'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let browser,stderr='';fixture.stderr.on('data',b=>stderr+=b);
 try{
  const info=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(stderr)),20000);fixture.stdout.on('data',b=>{out+=b;for(const line of out.split('\n'))try{const d=JSON.parse(line);if(d.port){clearTimeout(timer);resolve(d)}}catch{}});fixture.on('exit',()=>{clearTimeout(timer);reject(Error(stderr))})});
  browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],base='http://127.0.0.1:'+info.port;
  page.on('pageerror',e=>errors.push(e.message));
  assert.equal((await page.request.post(base+'/api/login',{data:{username:'fixture',password:'fixture-password'},headers:{'X-Sprite-Request':'1'}})).status(),200);
  const before=await (await page.request.get(base+`/api/images/${source}/image-1.png`)).body();let jobId,submits=0;
  page.on('response',async r=>{if(r.url().endsWith('/face-refine')&&r.status()===202){jobId=(await r.json()).jobId;submits++}});
  await page.goto(base+'/#/jobs/'+source);await page.getByRole('button',{name:'얼굴만 보정',exact:true}).click();
  await page.locator('#faceRefineDialog').waitFor({state:'visible'});assert.equal(await page.locator('#faceRefineStrength').inputValue(),'0.12');
  await page.screenshot({path:path.join(root,'outputs/face-refine-dialog.png'),fullPage:true});
  await page.locator('#startFaceRefine').click();
  console.log(real?'Running actual detected-face refinement':'Running explicit fake face fixture');
  await page.locator('#faceRefineComparison canvas').nth(1).waitFor({state:'visible',timeout:240000});
  await page.getByRole('link',{name:'보정 PNG 저장',exact:true}).waitFor();
  assert.equal(submits,1);assert(jobId);const job=await (await page.request.get(base+'/api/jobs/'+jobId)).json();
  assert.equal(job.state,'complete');assert.equal(job.settings.parentJob,source);assert.equal(job.settings.operation,'face-refine');
  if(real)assert.equal(job.images[0].faceDetailApplied,true,'Real detector must find a face in the known sprite');
  assert.deepEqual(await (await page.request.get(base+`/api/images/${source}/image-1.png`)).body(),before);
  await page.screenshot({path:path.join(root,`outputs/face-refine-${real?'real':'fixture'}-comparison.png`),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(root,'outputs/face-refine-mobile.png'),fullPage:true});
  await page.locator('#faceRefineDialog').getByRole('button',{name:'닫기',exact:true}).click();
  await page.goto(base+'/#/jobs/'+jobId);await page.getByRole('button',{name:'얼굴 전후 비교',exact:true}).click();
  await page.locator('#faceRefineComparison canvas').nth(1).waitFor({state:'visible'});
  await page.locator('#faceRefineDialog').getByRole('button',{name:'닫기',exact:true}).click();
  // The same button is available on an existing result in the studio itself.
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/#/create/image');const f=page.frameLocator('#imageStudio');
  await f.locator('#model option[value="wai-cutscene-counter"]').waitFor({state:'attached'});
  const child=page.frames().find(t=>t.url().includes('/image-studio'));
  await child.evaluate(job=>showResults(job),job);
  await f.getByRole('button',{name:'얼굴만 보정',exact:true}).click();await f.locator('#faceRefineDialog').waitFor({state:'visible'});
  assert.equal(await f.locator('#faceRefineStrength').inputValue(),'0.12');
  assert.deepEqual(errors,[]);
  if(real)fs.writeFileSync(path.join(info.imageRoot,'face-refine-test.json'),JSON.stringify({source,jobId,job,originalPreserved:true,errors},null,2));
  console.log('PASS: gallery + studio face button, one queued request, before/after, original preserved, separate gallery result, mobile. '+(real?info.imageRoot:''));
 }finally{if(browser)await browser.close();fixture.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
