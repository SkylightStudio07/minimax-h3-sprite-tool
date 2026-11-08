/* Real pointer/keyboard masking regression; all APIs mocked, no GPU work. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];let submitted;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://mask.test/**',route=>{const u=new URL(route.request().url());
  if(u.pathname==='/rigging')return route.fulfill({path:path.join(root,'web/rigging.html')});
  if(u.pathname.startsWith('/assets/'))return route.fulfill({path:path.join(root,'web',u.pathname)});
  if(u.pathname==='/api/me')return route.fulfill({json:{user:{id:1,name:'test',role:'admin'}}});
  if(u.pathname==='/api/rigging/generate'){submitted=route.request().postDataJSON();return route.fulfill({json:{jobId:'mask-test'}})}
  if(u.pathname==='/api/jobs/mask-test')return route.fulfill({json:{state:'cancelled',message:'mock finished'}});
  if(u.pathname==='/api/jobs')return route.fulfill({json:{jobs:[]}});
  return route.fulfill({json:{}});
 });
 await page.goto('http://mask.test/rigging');
 const data=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=1000;c.height=1200;const x=c.getContext('2d');x.fillStyle='#f6e1d8';x.fillRect(0,0,1000,1200);for(const px of [300,700]){x.fillStyle='#453b4d';x.fillRect(px-65,250,130,12);x.fillStyle='white';x.beginPath();x.ellipse(px,350,65,35,0,0,Math.PI*2);x.fill();x.fillStyle='#5875b2';x.beginPath();x.arc(px,350,30,0,Math.PI*2);x.fill()}x.strokeStyle='#a34d62';x.lineWidth=10;x.beginPath();x.ellipse(500,650,40,10,0,0,Math.PI*2);x.stroke();return c.toDataURL('image/png')});
 await page.locator('#file').setInputFiles({name:'mask-fixture.png',mimeType:'image/png',buffer:Buffer.from(data.split(',')[1],'base64')});
 await page.locator('#maskPane').waitFor();await page.locator('#canvasScroll').scrollIntoViewIfNeeded();
 async function zoom(value){await page.locator('#zoom').evaluate((e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}))},String(value))}
 async function draw(x,y,dx=20){const box=await page.locator('#maskCanvas').boundingBox(),factor=Number(await page.locator('#zoom').inputValue())/100;await page.mouse.move(box.x+x*factor,box.y+y*factor);await page.mouse.down();await page.mouse.move(box.x+(x+dx)*factor,box.y+y*factor,{steps:4});await page.mouse.up()}
 async function metrics(label){return page.evaluate(label=>maskMetrics(label),label)}
 await zoom(50);await page.locator('#canvasScroll').focus();
 await draw(400,350);const left=(await metrics('eyeLeft')).count;assert(left>0);
 await page.keyboard.press('2');assert.equal(await page.locator('[data-tool="eyeRight"]').getAttribute('aria-pressed'),'true');
 await draw(400,350);assert((await metrics('eyeRight')).count>0);
 await page.keyboard.press('e');await page.locator('#brush').evaluate(e=>{e.value='160';e.dispatchEvent(new Event('input'))});await page.locator('#canvasScroll').focus();await draw(400,350);
 assert.equal((await metrics('eyeRight')).count,0);assert.equal((await metrics('eyeLeft')).count,left);
 assert.equal(await page.locator('#maskErase').getAttribute('aria-pressed'),'true');assert((await page.locator('#maskToolStatus').textContent()).includes('오른쪽 눈'));
 await page.keyboard.press('Control+z');assert((await metrics('eyeRight')).count>0);
 await page.keyboard.press('Control+Shift+z');assert.equal((await metrics('eyeRight')).count,0);
 await page.keyboard.press('Control+z');await page.keyboard.press('b');assert.equal(await page.locator('#brush').inputValue(),'160');
 const beforeClear=await page.evaluate(()=>exportMask('eyeLeft'));await page.locator('#clearMasks').click();assert.equal((await metrics('eyeLeft')).count,0);await page.locator('#undo').click();assert.equal(await page.evaluate(()=>exportMask('eyeLeft')),beforeClear);
 await page.locator('#maskClearRegion').click();assert.equal((await metrics('eyeRight')).count,0);assert.equal((await metrics('eyeLeft')).count,left);await page.locator('#maskRedo').isDisabled();
 await page.locator('#undo').click();
 const exported=await page.evaluate(()=>exportMask('eyeLeft'));
 await page.locator('#maskOpacity').evaluate(e=>{e.value='80';e.dispatchEvent(new Event('input'))});assert.equal(await page.locator('#maskCanvas').evaluate(e=>e.style.opacity),'0.8');assert.equal(await page.evaluate(()=>exportMask('eyeLeft')),exported);
 await page.locator('#canvasScroll').focus();await page.keyboard.press('q');assert.equal(await page.locator('#maskCanvas').evaluate(e=>e.style.opacity),'0');assert.equal(await page.evaluate(()=>exportMask('eyeLeft')),exported);await page.keyboard.press('q');
 await zoom(200);await page.locator('#canvasScroll').evaluate(e=>{e.scrollLeft=100;e.scrollTop=100});
 const count=await page.evaluate(()=>strokes.length),scroll=await page.locator('#canvasScroll').boundingBox();await page.locator('#canvasScroll').focus();await page.keyboard.down('Space');await page.mouse.move(scroll.x+200,scroll.y+200);await page.mouse.down();await page.mouse.move(scroll.x+120,scroll.y+140);await page.mouse.up();await page.keyboard.up('Space');assert.equal(await page.evaluate(()=>strokes.length),count);assert((await page.locator('#canvasScroll').evaluate(e=>e.scrollLeft))>150);
 const oldZoom=Number(await page.locator('#zoom').inputValue());await page.mouse.move(scroll.x+200,scroll.y+200);await page.keyboard.down('Control');await page.mouse.wheel(0,-100);await page.keyboard.up('Control');assert.equal(Number(await page.locator('#zoom').inputValue()),oldZoom+25);
 await page.locator('#canvasScroll').focus();await page.keyboard.press('Control+0');const fit=await page.evaluate(()=>({w:maskCanvas.getBoundingClientRect().width,h:maskCanvas.getBoundingClientRect().height,cw:$('canvasScroll').clientWidth,ch:$('canvasScroll').clientHeight}));assert(fit.w<=fit.cw&&fit.h<=fit.ch);
 await page.keyboard.press('Control+1');assert.equal(await page.locator('#zoom').inputValue(),'100');assert.equal(await page.locator('#maskCanvas').evaluate(e=>e.style.width),'1000px');
 await page.locator('#seed').fill('');await page.locator('#seed').press('b');assert.equal(await page.locator('#seed').inputValue(),'b');await page.locator('#seed').fill('');
 await zoom(50);await page.locator('input[name=eyeMode][value=closed-stroke]').check();await page.locator('#canvasScroll').focus();await page.keyboard.press('1');await page.keyboard.press('e');await draw(400,350);await page.locator('input[name=eyeMode][value=area]').check();assert.equal((await metrics('eyeLeft')).count,left);
 await page.locator('#canvasScroll').focus();await page.keyboard.press('5');await page.keyboard.press('b');await draw(500,650);assert((await metrics('mouth')).count>0);assert.equal(await page.evaluate(()=>validateMasks().mode),'area');
 await page.locator('#generate').click();await page.waitForFunction(()=>document.getElementById('status').textContent==='mock finished');assert.equal(submitted.eyeInputMode,'area');assert.equal(submitted.maskVersion,1);assert(submitted.eyeLeftMask.startsWith('data:image/png'));assert(submitted.eyeRightMask.startsWith('data:image/png'));assert(submitted.mouthMask.startsWith('data:image/png'));
 await page.screenshot({path:path.join(root,'outputs','rigging-mask-tools-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('.creation-mobile-tabs button').filter({hasText:'작업 화면'}).click();await page.locator('#maskPane').scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 await page.locator('#maskWorkTab').click();await page.locator('#maskFit').click();assert.equal(await page.locator('#maskWork').isVisible(),true);
 await page.screenshot({path:path.join(root,'outputs','rigging-mask-tools-mobile.png'),fullPage:true});
 await page.setViewportSize({width:1280,height:1000});await page.addStyleTag({url:'http://mask.test/assets/ui.css'});await page.addStyleTag({url:'http://mask.test/assets/embed-legacy.css'});await page.evaluate(()=>{document.documentElement.classList.add('embedded-studio');document.documentElement.dataset.theme='light'});
 await page.locator('#canvasScroll').scrollIntoViewIfNeeded();await page.locator('#canvasScroll').focus();await page.keyboard.press('e');await page.keyboard.press('1');assert.equal(await page.locator('#maskErase').getAttribute('aria-pressed'),'true');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 await page.screenshot({path:path.join(root,'outputs','rigging-mask-tools-embedded-light.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: region shortcuts, scoped erase, undo/redo/clear, opacity, pan, zoom, input guard, eye modes, validation, mobile');
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
