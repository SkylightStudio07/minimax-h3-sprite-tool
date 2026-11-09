/* Full-shell geometry and workspace journeys. Mocked APIs; no production jobs or accounts. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const sample=path.join(root,'outputs/reference-battle-adjust-20261018/outfit-080.png');
const source=fs.existsSync(sample)?fs.readFileSync(sample):Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];let writes=0;
 page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack)});
 await page.route('http://workspace.test/**',async route=>{
  const req=route.request(),u=new URL(req.url()),files={'/':'team.html','/image-studio':'image-studio.html','/studio':'index.html','/rigging':'rigging.html'};
  if(req.method()!=='GET'){writes++;return route.fulfill({status:500,json:{error:'Test must not submit work'}})}
  if(files[u.pathname]||u.pathname.startsWith('/assets/')){const file=path.join(root,'web',files[u.pathname]||u.pathname.slice(1));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404})}
  if(u.pathname==='/fixture.png')return route.fulfill({contentType:'image/png',body:source});
  let data={};
  if(u.pathname==='/api/me')data={user:{id:1,name:'작업자',role:'admin',state:'approved'},setupRequired:false};
  else if(u.pathname==='/api/jobs')data={jobs:[]};
  else if(u.pathname==='/api/characters')data={characters:[]};
  else if(u.pathname==='/api/users')data={users:[]};
  else if(u.pathname==='/api/gallery')data={jobs:[],pages:1,page:1,total:0};
  else if(u.pathname==='/api/public-live2d')data={items:[]};
  else if(u.pathname==='/api/me/summary')data={counts:{},active:0,activeLimit:3,shares:[],publicLive2d:[]};
  else if(u.pathname==='/api/status')data={comfy:true,modelsReady:true,licenseConfirmed:true,spriteBackground:{ready:true},rigging:{comfy:true,modelsReady:true},spriteWorkflows:[]};
  else if(u.pathname==='/api/images/models')data={comfy:true,background:{ready:true},caption:{ready:true},pose:{ready:false,models:[]},faceDetail:{ready:false,models:[]},styles:[],models:[{id:'soya-anima-flanime',name:'기본 일러스트',ready:true,family:'anima',steps:16,cfg:2,modes:['text'],defaultSize:'768x768'},{id:'wai-cutscene-counter',name:'셀 채색',ready:true,family:'illustrious',steps:28,cfg:4.5,modes:['text','reference','inpaint'],defaultSize:'832x1216'}]};
  return route.fulfill({json:data});
 });
 const getFrame=id=>page.frames().find(f=>f===page.mainFrame()?false:f.frameElement&&f.url().includes(id));
 const layoutState=async frame=>frame.evaluate(()=>{const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height,right:b.right,bottom:b.bottom}};return{width:innerWidth,height:innerHeight,scrollW:document.documentElement.scrollWidth,scrollH:document.documentElement.scrollHeight,settings:r('.creation-settings'),footer:r('.creation-submit'),output:r('.creation-output'),toolbar:r('.creation-toolbar')}});
 for(const [routeName,id,urlName] of [['image','imageStudio','image-studio'],['sprite','studio','/studio'],['rig','riggingStudio','/rigging']]){
  await page.goto('http://workspace.test/#/create/'+routeName);const frame=page.frameLocator('#'+id);
  await frame.locator('body[data-creation-workspace="ready"]').waitFor();const inner=getFrame(urlName);
  if(routeName==='sprite')await frame.locator('#spriteAdvanced').evaluate(d=>{d.open=true});
  const beforeScroll=await layoutState(inner);
  const scroll=await inner.evaluate(()=>{const x=document.querySelector('.creation-settings-scroll');x.scrollTop=x.scrollHeight;return x.scrollTop});assert(scroll>0,'settings actually scroll independently');
  const afterScroll=await layoutState(inner);assert.equal(afterScroll.output.y,beforeScroll.output.y);assert.equal(afterScroll.footer.bottom,beforeScroll.footer.bottom);
  await inner.evaluate(()=>document.querySelector('.creation-settings-scroll').scrollTop=0);
  for(const width of [1920,1440,1024]){
   await page.setViewportSize({width,height:1000});
   const shell=await page.locator('#'+id).boundingBox(),m=await layoutState(inner);
   assert(Math.abs(shell.x+shell.width-width)<2,'iframe reaches right viewport edge');
   assert(Math.abs(m.output.right-m.width)<2,'work area reaches right edge');assert(m.output.w>m.width*.55,'most width belongs to output');
   assert(m.settings.w>=300&&m.settings.w<=380);assert(m.footer.bottom<=m.height+1,'generate stays visible');
   assert(m.scrollW<=m.width+1&&m.scrollH<=m.height+1,'no outer scrolling');
  }
  if(routeName==='image'){
   await inner.evaluate(()=>{document.getElementById('resultEmpty').hidden=true;showResults({id:'fixture',settings:{model:'soya-anima-flanime'},images:[1,2,3].map(seed=>({url:'/fixture.png?seed='+seed,seed,background:'keep'}))})});
   await frame.locator('#results img').nth(1).click();assert.equal(await frame.locator('.creation-candidate-count').textContent(),'2 / 3');
   assert.equal(await frame.locator('#results article:visible').count(),1);
   await frame.getByRole('button',{name:'다음 후보',exact:true}).click();assert.equal(await frame.locator('.creation-candidate-count').textContent(),'3 / 3');
   await frame.getByRole('button',{name:'후보 목록으로 보기',exact:true}).click();assert.equal(await frame.locator('#results article:visible').count(),3);
   await frame.locator('#prompt').fill('silver hair, dark coat');
  }else{
   await frame.locator('#file').setInputFiles({name:'character.png',mimeType:'image/png',buffer:source});
   if(routeName==='rig'){await frame.locator('#maskCanvas').waitFor();await frame.locator('.creation-region').selectOption('mouth');assert.equal(await frame.locator('[data-tool=mouth]').getAttribute('aria-pressed'),'true')}
   else await frame.locator('.creation-source-image').waitFor();
  }
  await page.setViewportSize({width:1920,height:1080});await page.screenshot({path:path.join(root,'outputs','creation-workspace-'+routeName+'.png')});
  if(routeName==='image'){await page.locator('#app [data-theme-toggle]').click();await page.screenshot({path:path.join(root,'outputs','creation-workspace-image-dark.png')});await page.locator('#app [data-theme-toggle]').click()}
  for(const width of [768,390,320]){
   await page.setViewportSize({width,height:844});const m=await layoutState(inner);assert(m.scrollW<=m.width+1&&m.scrollH<=m.height+1);
   if(width<=390){
    await frame.locator('.creation-mobile-tabs button').filter({hasText:'설정'}).click();assert(await frame.locator('#generate').isVisible());
    await frame.locator('.creation-mobile-tabs button').filter({hasText:'작업 화면'}).click();assert(await frame.locator('.creation-output').isVisible());
    assert.equal(await frame.locator('.creation-settings').isVisible(),false);
    const image=routeName==='image'?'#results img':routeName==='rig'?'#maskCanvas':'.creation-source-image';assert(await frame.locator(image).first().isVisible());
   }
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(root,'outputs','creation-workspace-'+routeName+'-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  if(routeName==='image')assert.equal(await frame.locator('#prompt').inputValue(),'silver hair, dark coat');
 }
 assert.equal(writes,0);assert.deepEqual(errors,[]);
 console.log('PASS: 3 full-shell workspaces, 1920/1440/1024/768/390/320, right-edge fill, fixed generation, independent scrolling, gallery/stage selection, source upload, rig region selection, mobile switch, preserved form, no writes.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
