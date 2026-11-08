// Browser authoring regression with mocked APIs; never changes production jobs.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVR4nGPcYmT0nwEPYMInOXwUAAArdAIn9t4S0wAAAABJRU5ErkJggg==','base64');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];let saved=null;
  page.on('pageerror',e=>errors.push(e.message));
  const layer={id:'mouth_close',key:'expression:mouth_close',kind:'expression',runtimeName:'mouth_close',left:40,top:40,width:8,height:8,defaultVisible:true,asset:'/fixture.png',originalAsset:'/fixture.png'};
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/rigging-editor')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'web/rigging-editor.html'),'utf8')});
   if(url.pathname.startsWith('/assets/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':url.pathname.endsWith('.js')?'text/javascript':'font/woff2',body:fs.readFileSync(path.join(root,'web',url.pathname))});
   if(url.pathname==='/rigging-expressions.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'web/rigging-expressions.js'),'utf8')});
   if(url.pathname==='/rigging-bones.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'web/rigging-bones.js'),'utf8')});
   if(['/rigging-animation.js','/rigging-animation-math.js'].includes(url.pathname))return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'web',path.basename(url.pathname)),'utf8')});
   if(url.pathname==='/fixture.png')return route.fulfill({contentType:'image/png',body:png});
   if(url.pathname.endsWith('/revisions')){saved=route.request().postDataJSON();return route.fulfill({json:{revision:1}})}
   if(url.pathname.endsWith('/rig-edit'))return route.fulfill({json:{canvas:{width:96,height:96},revision:saved?1:0,layers:[layer],versions:[]}});
   return route.fulfill({status:404,body:'Not found'});
  });
  await page.goto('http://sprite.test/rigging-editor?job=test');
  await page.waitForFunction(()=>model&&parts.length===1).catch(async error=>{console.error(errors,await page.locator('#status').textContent());throw error});
  await page.locator('#expressionName').fill('웃는 입');await page.locator('#newExpression').click();
  assert.equal(await page.evaluate(()=>selected.variantOf),'expression:mouth_close');
  await page.evaluate(()=>{setZoom(400);$('size').value='4';$('inkColor').value='#234567'});
  const box=await page.locator('#canvas').boundingBox();
  await page.mouse.move(box.x+44*4,box.y+44*4);await page.mouse.down();await page.mouse.move(box.x+47*4,box.y+44*4,{steps:4});await page.mouse.up();
  assert.deepEqual(await page.evaluate(()=>Array.from(selected.canvas.getContext('2d').getImageData(28,28,1,1).data)),[35,69,103,255]);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>selected.canvas.getContext('2d').getImageData(28,28,1,1).data[3]),0);
  await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>selected.canvas.getContext('2d').getImageData(28,28,1,1).data[3]),255);
  await page.locator('#applyExpression').click();assert.equal(await page.evaluate(()=>history.at(-1).kind),'variant_apply');
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>Boolean(selected.variantOf)),true);
  await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>history.at(-1).kind),'variant_apply');
  await page.locator('#save').click();await page.waitForFunction(()=>model.revision===1);
  assert.deepEqual(saved.operations.map(o=>o.kind),['variant_create','paint','variant_apply']);
  assert.equal(saved.operations[1].color,'#234567');assert(!JSON.stringify(saved).includes('localPart'));
  await page.locator('#copyExpression').click();
  // The canvas bitmap is independent of the machine's display scale.
  const image=Buffer.from(await page.evaluate(()=>canvas.toDataURL('image/png').split(',')[1]),'base64');
  await page.locator('#expressionFile').setInputFiles({name:'mouth.png',mimeType:'image/png',buffer:image});
  await page.waitForFunction(()=>history.at(-1)?.kind==='variant_png',{},{timeout:5000}).catch(async error=>{console.error(await page.locator('#status').textContent(),await page.evaluate(()=>({saving,selected:selected?.id,ops:history.map(o=>o.kind),size:[canvas.width,canvas.height],css:[canvas.style.width,canvas.style.height]})),errors);throw error});
  await page.keyboard.press('Control+z');await page.keyboard.press('Control+y');
  await page.keyboard.press('Control+z'); // import
  await page.keyboard.press('Control+z'); // create
  assert.equal(await page.evaluate(()=>parts.filter(p=>p.variantOf).length),0);
  await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>parts.filter(p=>p.variantOf).length),1);
  assert.deepEqual(errors,[]);
  console.log('Expression browser flow passed: drawing, undo/redo, apply, save, PNG, create undo.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
