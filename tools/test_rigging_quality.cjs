/* Isolated quality-tool flow; never changes a production rig. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];let revision=0,submitted,readonly=false;
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://quality.test/**',route=>{const u=new URL(route.request().url());
  if(u.pathname==='/rigging-editor')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'web/rigging-editor.html'),'utf8')});
  if(u.pathname.startsWith('/assets/')||/^\/rigging-.*\.js$/.test(u.pathname))return route.fulfill({path:path.join(root,'web',u.pathname)});
  if(u.pathname==='/fixture.png')return route.fulfill({contentType:'image/png',body:png});
  if(u.pathname.endsWith('/rig-edit/upscale')){submitted=route.request().postDataJSON();revision++;return route.fulfill({json:{revision,scale:submitted.scale}})}
  if(u.pathname.endsWith('/rig-edit')){const size=96*2**revision;return route.fulfill({json:{canvas:{width:size,height:size},revision,readonly,upscale:{aiReady:true},layers:[{id:'face',key:'part:face',kind:'part',runtimeName:'face',file:'layers/face.png',left:0,top:0,width:size,height:size,asset:'/fixture.png',originalAsset:'/fixture.png'}],versions:[]}})}
  return route.fulfill({status:404,body:''});
 });
 await page.goto('http://quality.test/rigging-editor?job=test&mode=quality');
 await page.waitForFunction(()=>document.getElementById('upscaleMethod').value==='anime-ai');
 await page.locator('#qualityTool').click();assert((await page.locator('#upscaleSize').textContent()).includes('192'));
 await page.locator('#applyUpscale').click();await page.waitForFunction(()=>model.revision===1&&!saving);
 assert.equal(submitted.method,'anime-ai');assert.equal(submitted.revision,0);assert.equal(submitted.scale,2);assert.equal(submitted.action,'apply');
 assert.equal(await page.locator('#canvas').getAttribute('width'),'192');
 await page.evaluate(()=>{history.push({kind:'test'});updateActions()});submitted=null;
 await page.locator('#applyUpscale').click();assert.equal(submitted,null);assert((await page.locator('#status').textContent()).includes('먼저 저장'));
 await page.evaluate(()=>{history=[];updateActions()});
 await page.setViewportSize({width:390,height:844});await page.locator('#qualityTool').click();assert.equal(await page.locator('#qualityPanel').isVisible(),true);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 readonly=true;await page.evaluate(()=>load());assert.equal(await page.locator('#qualityTool').isVisible(),false);
 assert.deepEqual(errors,[]);console.log('PASS: quality entry, AI default, apply/new revision, dirty guard, mobile, readonly');
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
