// Real video decode and workspace export on a disposable app; no inference.
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tools/serve_character_fixture.py'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let stderr='';fixture.stderr.on('data',b=>stderr+=b);
 const port=await new Promise((resolve,reject)=>{let out='';const timeout=setTimeout(()=>reject(Error(stderr)),15000);fixture.stdout.on('data',b=>{out+=b;try{const d=JSON.parse(out.trim().split('\n').at(-1));clearTimeout(timeout);resolve(d.port)}catch{}});fixture.on('exit',()=>{clearTimeout(timeout);reject(Error(stderr))})});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const base='http://127.0.0.1:'+port,page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.request.post(base+'/api/login',{data:{username:'fixture',password:'fixture-password'},headers:{'X-Sprite-Request':'1'}});
  await page.goto(base+'/loop-editor?job=sprite');await page.locator('#workspace').waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelector('#video').readyState>=2);
  assert((await page.locator('#position').textContent()).includes('/ 24장'));
  async function seek(frame){await page.locator('#timeline').fill(String(frame));await page.waitForFunction(frame=>Number(document.querySelector('#timeline').value)===frame,frame)}
  await seek(4);await page.locator('#markStart').click();await seek(19);await page.locator('#markEnd').click();assert((await page.locator('#rangeSummary').textContent()).includes('16프레임'));
  await page.locator('#startNext').click();assert((await page.locator('#startLabel').textContent()).includes('6번째'));await page.locator('#startPrevious').click();
  await page.locator('#count').selectOption('8');assert.equal(await page.locator('#fps').inputValue(),'6');assert((await page.locator('#samplingNote').textContent()).includes('8장'));
  await page.locator('#preview').click();await page.waitForTimeout(350);assert.equal(await page.locator('#preview').textContent(),'반복 재생 정지');await page.locator('#preview').click();
  await page.locator('#boundaryPlay').click();await page.waitForTimeout(500);await page.locator('#boundaryPlay').click();
  await page.locator('summary').click();await page.waitForFunction(()=>['firstImage','lastImage','overlayFirst','overlayLast'].every(id=>document.getElementById(id).naturalWidth>0));
  await page.screenshot({path:path.join(root,'outputs/loop-editor-desktop.png'),fullPage:true});
  let payload;page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/loop-editor'))payload=r.postDataJSON()});
  await page.locator('#save').click();await page.locator('#result').waitFor({state:'visible'});assert.deepEqual(payload,{source:'video',start:4,end:19,count:8,fps:6,background:'keep'});
  const href=await page.locator('#edit').getAttribute('href'),wid=new URL(base+href).searchParams.get('set');
  const doc=await (await page.request.get(base+'/api/frames/'+wid)).json();assert.equal(doc.frames.length,8);assert.equal(doc.frames[0].sourceFrame,4);assert.equal(doc.frames.at(-1).sourceFrame,19);assert.equal(doc.fps,6);
  const zip=await page.request.get(base+await page.locator('#download').getAttribute('href'));assert.equal(zip.status(),200);assert((await zip.body()).length>1000);
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(root,'outputs/loop-editor-mobile.png'),fullPage:true});
  await page.locator('#edit').click();await page.locator('#frameMain').waitFor({state:'visible'});assert.equal(await page.locator('.frame-thumb').count(),8);assert.equal(await page.locator('#frameFPS').inputValue(),'6');assert(await page.locator('#frameVideoLoop').isVisible());
  await page.goto(base+'/#/jobs/sprite');await page.getByRole('link',{name:'반복 구간 고르기',exact:true}).waitFor();
  assert.deepEqual(errors,[]);console.log('PASS manual video loop: exact frame markers, nudges, boundary preview, output count/FPS, real ZIP export, frame workspace, entry and mobile.');
 }finally{await browser.close();fixture.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
