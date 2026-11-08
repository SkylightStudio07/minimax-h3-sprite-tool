/* Pixel creation UX with mocked GPU/model state; no production mutations. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];let ready=false,submitted;
 page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack)});
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
 const result={id:'pixel-test',jobType:'image',state:'complete',settings:{model:'pixel-art-xl',preset:'sprite',pixelSize:64,pixelColors:16,width:1024,height:1024},images:[{url:'/fixture.png',seed:42,pixelArt:true,width:64,height:64,pixelColors:16,pixelPreviewUrl:'/fixture.png?preview',beforePixelUrl:'/fixture.png?before'}]};
 await page.route('http://pixel.test/**',async route=>{
  const u=new URL(route.request().url()),name=u.pathname;
  if(name==='/image-studio')return route.fulfill({path:path.join(root,'web/image-studio.html')});
  if(name.startsWith('/assets/')){const file=path.join(root,'web',name);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404})}
  if(name==='/fixture.png')return route.fulfill({contentType:'image/png',body:png});
  let data={};
  if(name==='/api/images/models')data={comfy:true,styles:[],background:{ready:false},caption:{ready:false},pose:{ready:false,models:[]},faceDetail:{ready:false,models:[]},models:[{id:'soya-anima-flanime',ready:true,name:'기본 일러스트',family:'anima',steps:16,cfg:2,defaultSize:'768x768',modes:['text']},{id:'pixel-art-xl',ready,name:'픽셀 아트',family:'pixel-sdxl',steps:30,cfg:7,defaultSize:'1024x1024',modes:['text','reference']}]};
  else if(name==='/api/characters')data={characters:[]};
  else if(name==='/api/images/generate'){submitted=route.request().postDataJSON();data={jobId:'pixel-test'}}
  else if(name==='/api/jobs/pixel-test')data=result;
  return route.fulfill({json:data});
 });
 await page.goto('http://pixel.test/image-studio');await page.waitForFunction(()=>models.length===2);
 await page.locator('[data-task=pixel]').click();assert(await page.locator('#pixelControls').isVisible());assert(await page.locator('#generate').isDisabled());assert((await page.locator('#pixelReady').textContent()).includes('준비 중'));
 assert.equal(await page.locator('#model').inputValue(),'pixel-art-xl');assert.equal(await page.locator('[data-task=pixel]').getAttribute('aria-pressed'),'true');
 ready=true;await page.reload();await page.waitForFunction(()=>models.length===2);await page.locator('[data-task=pixel]').click();
 await page.locator('#pixelSize').selectOption('64');await page.locator('#pixelColors').selectOption('16');
 assert((await page.locator('#generationSummary').textContent()).includes('64 × 64'));assert.equal(await page.locator('#size').inputValue(),'1024x1024');
 assert(await page.locator('#faceDetail').isDisabled());assert(await page.locator('#hiresFix').isDisabled());assert(await page.locator('#libraryToggle').isHidden());
 await page.locator('#pixelInput').selectOption('reference');assert(await page.locator('#referenceSetup').isVisible());
 await page.locator('#prompt').fill('red knight');await page.locator('#generate').click();assert.equal(submitted,undefined);
 await page.locator('#file').setInputFiles({name:'reference.png',mimeType:'image/png',buffer:png});await page.waitForFunction(()=>sourceData.length>0);
 await page.locator('#generate').click();await page.locator('#results article').waitFor();await page.waitForFunction(()=>!busy);
 assert.equal(submitted.model,'pixel-art-xl');assert.equal(submitted.pixelSize,64);assert.equal(submitted.pixelColors,16);assert.equal(submitted.mode,'reference');assert.equal(submitted.width,1024);assert.equal(submitted.height,1024);assert(!submitted.assetSpec);assert(!submitted.pose);assert(!submitted.styleId);assert(!submitted.hiresFix);assert(!submitted.faceDetail);
 assert.equal(await page.locator('#results button').filter({hasText:'얼굴만 보정'}).count(),0);
 assert.equal(await page.locator('#results img').evaluate(img=>getComputedStyle(img).imageRendering),'pixelated');assert((await page.locator('#results').textContent()).includes('64×64'));assert.equal(await page.locator('#results a').filter({hasText:'8배 미리보기'}).count(),1);
 await page.locator('#results button').filter({hasText:'원본 참고로 다시 만들기'}).click();await page.waitForFunction(()=>document.getElementById('mode').value==='reference');assert.equal(await page.locator('#pixelSize').inputValue(),'64');assert.equal(await page.locator('#pixelColors').inputValue(),'16');assert.equal(await page.locator('[data-task=pixel]').getAttribute('aria-pressed'),'true');
 await page.screenshot({path:path.join(root,'outputs/pixel-studio-desktop.png')});
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(root,'outputs/pixel-studio-mobile.png')});
 await page.locator('[data-task=create]').click();assert.equal(await page.locator('#model').inputValue(),'soya-anima-flanime');assert(await page.locator('#pixelControls').isHidden());assert.equal(await page.locator('#prompt').inputValue(),'red knight');
 assert.deepEqual(errors,[]);console.log('PASS: pixel download gate, sizes/palette, fixed recipe, reference validation, lowres result, crisp preview, restore, mobile, returning to illustration.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
