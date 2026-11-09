// Full local HTTP integration with disposable SQLite/files. AI completion is simulated explicitly.
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tools/serve_character_fixture.py'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let stderr='';fixture.stderr.on('data',b=>stderr+=b);
 const port=await new Promise((resolve,reject)=>{let out='';const timeout=setTimeout(()=>reject(Error('Fixture startup: '+stderr)),15000);fixture.stdout.on('data',b=>{out+=b;try{const d=JSON.parse(out.trim().split('\n').at(-1));clearTimeout(timeout);resolve(d.port)}catch{}});fixture.on('exit',()=>reject(Error(stderr)))});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const base='http://127.0.0.1:'+port,page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const login=await page.request.post(base+'/api/login',{data:{username:'fixture',password:'fixture-password'},headers:{'X-Sprite-Request':'1'}});assert.equal(login.status(),200);
  await page.goto(base+'/character-studio');await page.locator('#newName').fill('정찰병 테스트');await page.locator('#newCharacter button').click();await page.getByRole('heading',{name:'이 캐릭터로 이어 만들기'}).waitFor();
  const cid=new URL(page.url()).searchParams.get('character');assert(cid);
  const jobs=page.locator('.character-attach select');await jobs.nth(0).selectOption('sprite');await jobs.nth(1).selectOption('motion');await jobs.nth(2).selectOption('right');await page.locator('.character-attach input').fill('걷기');await page.getByRole('button',{name:'묶음에 연결',exact:true}).click();await page.getByText('걷기 · 완료',{exact:false}).waitFor();
  await jobs.nth(0).selectOption('art');await jobs.nth(1).selectOption('art');await page.getByRole('button',{name:'묶음에 연결',exact:true}).click();await page.getByRole('button',{name:'기본 그림체로 보관'}).click();await page.getByText('기본 그림체 설정이 보관되어 있어요.',{exact:false}).waitFor();
  const art=await page.request.get(base+'/api/images/art/image-1.png');await page.locator('input[type=file]').setInputFiles({name:'reference.png',mimeType:'image/png',buffer:await art.body()});await page.locator('img[alt="대표 원화"]').waitFor();
  await page.screenshot({path:path.join(root,'outputs/character-studio-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(root,'outputs/character-studio-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/frame-editor?job=sprite&character='+cid);await page.locator('#importFrames').click();await page.locator('#frameMain').waitFor({state:'visible'});const wid=new URL(page.url()).searchParams.get('set');assert(wid);
  assert.equal(await page.locator('.frame-thumb').count(),4);await page.locator('#framePlay').click();await page.waitForTimeout(250);await page.locator('#framePlay').click();
  await page.locator('#lockOtherFrames').click();await page.waitForFunction(()=>document.querySelector('#frameVersion').textContent.includes('v2'));assert.equal(await page.locator('.frame-thumb').filter({hasText:'고정'}).count(),3);
  const canvas=page.locator('#frameCanvas'),box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.25);await page.mouse.down();await page.mouse.move(box.x+box.width*.6,box.y+box.height*.3,{steps:4});await page.mouse.up();
  await page.keyboard.press('Control+z');await page.keyboard.press('Control+Shift+z');await page.locator('#framePrompt').fill('눈을 자연스럽게 정리해 줘');
  await page.route('**/api/frames/*/candidates/*',async route=>{const task=new URL(route.request().url()).pathname.split('/').at(-1);await page.request.post(base+'/__fixture/finish/'+task,{data:{},headers:{'X-Sprite-Request':'1'}});await route.continue()});
  await page.locator('#generateFrame').click();await page.locator('#frameCandidate').waitFor({state:'visible'});await page.locator('#applyFrameCandidate').click();await page.waitForFunction(()=>document.querySelector('#frameVersion').textContent.includes('v3'));assert.equal(await page.locator('.frame-thumb').filter({hasText:'고정'}).count(),3);
  const exported=await page.request.get(base+'/api/frames/'+wid+'/export.zip');assert.equal(exported.status(),200);assert((await exported.body()).length>500);
  await page.locator('.frame-thumb').nth(1).click();assert.equal(await page.locator('#generateFrame').isDisabled(),true);
  page.on('dialog',dialog=>dialog.accept());await page.locator('#frameMarkStart').click();await page.locator('.frame-thumb').nth(2).click();await page.locator('#frameMarkEnd').click();assert((await page.locator('#frameRangeInfo').textContent()).includes('2장 선택'));await page.locator('#framePreviewRange').click();await page.waitForTimeout(150);await page.locator('#framePreviewRange').click();await page.locator('#frameTrim').click();await page.waitForFunction(()=>document.querySelectorAll('.frame-thumb').length===2);assert((await page.locator('#frameVersion').textContent()).includes('v4'));assert.equal(await page.locator('#frameTrim').isDisabled(),true);await page.locator('.frame-thumb').nth(1).click({modifiers:['Shift']});assert.equal(await page.locator('.frame-thumb').nth(1).getAttribute('data-dropped'),'true');assert((await page.locator('#framePickInfo').textContent()).includes('2장 중 1장'));await page.locator('#frameDropNone').click();assert.equal(await page.locator('#frameKeep').isDisabled(),true);await page.keyboard.press('x');assert.equal(await page.locator('#frameKeep').isDisabled(),false);await page.locator('#frameDropNone').click();
  await page.locator('#frameVersions').selectOption('2');await page.locator('#restoreFrameVersion').click();await page.waitForFunction(()=>document.querySelectorAll('.frame-thumb').length===4);assert((await page.locator('#frameVersion').textContent()).includes('v5'));
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(root,'outputs/frame-editor-mobile.png'),fullPage:true});
  await page.goto(base+'/#/characters');await page.frameLocator('#characterFrame').getByRole('heading',{name:'이 캐릭터로 이어 만들기'}).waitFor();
  await page.frameLocator('#characterFrame').getByRole('link',{name:'원화·스프라이트 만들기'}).click();
  const imageFrame=page.frameLocator('#imageStudio');await imageFrame.locator('#creationCharacter').waitFor();
  await page.waitForFunction(cid=>document.querySelector('#imageStudio').contentDocument?.querySelector('#creationCharacter')?.value===cid,cid);
  await imageFrame.locator('#useCharacterRecipe').click();
  assert.equal(await imageFrame.locator('#prompt').inputValue(),'hood, navy coat');
  await imageFrame.locator('#useCharacterArt').click();
  await page.waitForFunction(()=>document.querySelector('#imageStudio').contentDocument?.querySelector('#reference')?.width===32);
  assert.deepEqual(errors,[]);console.log('PASS character collection, attach, recipe, art, responsive, real frame APIs, mask, locks, candidate/apply, export and shell route.');
 }finally{await browser.close();fixture.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
