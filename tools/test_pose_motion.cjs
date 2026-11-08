// Retirement checks: no GPU inference or production accounts.
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tools/serve_character_fixture.py'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let stderr='';fixture.stderr.on('data',b=>stderr+=b);
 const port=await new Promise((resolve,reject)=>{let out='';const timeout=setTimeout(()=>reject(Error(stderr)),15000);fixture.stdout.on('data',b=>{out+=b;try{const d=JSON.parse(out.trim().split('\n').at(-1));clearTimeout(timeout);resolve(d.port)}catch{}});fixture.on('exit',()=>{clearTimeout(timeout);reject(Error(stderr))})});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const base='http://127.0.0.1:'+port,page=await browser.newPage();
  await page.request.post(base+'/api/login',{data:{username:'fixture',password:'fixture-password'},headers:{'X-Sprite-Request':'1'}});
  const before=(await (await page.request.get(base+'/api/jobs')).json()).jobs.length;
  const old=await page.request.get(base+'/motion-studio',{maxRedirects:0});assert.equal(old.status(),302);assert.equal(old.headers().location,'/#/create/sprite');
  for(const name of ['poses','templates']){const r=await page.request.get(base+'/api/motions/'+name);assert.equal(r.status(),410);assert.equal((await r.json()).retired,true)}
  const create=await page.request.post(base+'/api/motions',{data:{},headers:{'X-Sprite-Request':'1'}});assert.equal(create.status(),410);
  assert.equal((await (await page.request.get(base+'/api/jobs')).json()).jobs.length,before);
  for(const route of ['/character-studio','/frame-editor']){const r=await page.request.get(base+route);assert.equal(r.status(),200);assert(!(await r.text()).includes('href="/motion-studio'))}
  const script=await page.request.get(base+'/assets/character-studio.js');assert(!(await script.text()).includes('/motion-studio'));
  await page.goto(base+'/motion-studio');await page.waitForURL(base+'/#/create/sprite');
  console.log('PASS retired pose generation: redirect, HTTP 410, no new jobs, removed entry links.');
 }finally{await browser.close();fixture.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
