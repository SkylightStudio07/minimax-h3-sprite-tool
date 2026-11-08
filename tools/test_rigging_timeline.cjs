const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import rigging_bones,io,base64,json
from PIL import Image
manifest={'canvas':{'width':256,'height':384},'parts':[{'id':'body','left':20,'top':10,'width':210,'height':360},{'id':'arm_l','left':40,'top':100,'width':80,'height':110}],'expressions':[]}
buffer=io.BytesIO();Image.new('RGBA',(8,8),(70,90,140,255)).save(buffer,'PNG')
print(json.dumps({'rig':rigging_bones.get_rig(manifest),'layers':manifest['parts'],'png':base64.b64encode(buffer.getvalue()).decode()}))
`],{cwd:root,encoding:'utf8'}));
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});try{
  const page=await browser.newPage({viewport:{width:1550,height:1100},deviceScaleFactor:1}),errors=[];let saved=null,revision=0,animations=null,rig=fixture.rig;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{const url=new URL(route.request().url());if(url.pathname.startsWith('/assets/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':url.pathname.endsWith('.js')?'text/javascript':'font/woff2',body:fs.readFileSync(path.join(root,'web',url.pathname))});if(url.pathname==='/rigging-editor')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'web/rigging-editor.html'),'utf8')});if(url.pathname.endsWith('.js'))return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'web',path.basename(url.pathname)),'utf8')});if(url.pathname==='/fixture.png')return route.fulfill({contentType:'image/png',body:Buffer.from(fixture.png,'base64')});if(url.pathname.endsWith('/revisions')){saved=route.request().postDataJSON();const op=saved.operations.find(o=>o.kind==='rig_animation');animations=op.config;rig=op.rig;revision++;return route.fulfill({json:{revision}})}if(url.pathname.endsWith('/rig-edit'))return route.fulfill({json:{revision,canvas:{width:256,height:384},rig,rigAnimations:animations,versions:[],layers:fixture.layers.map(p=>({...p,key:'part:'+p.id,kind:'part',defaultVisible:true,asset:'/fixture.png',originalAsset:'/fixture.png'}))}});return route.fulfill({status:404})});
  await page.goto('http://sprite.test/rigging-editor?job=test');await page.waitForFunction(()=>boneState.rig&&activeClip());await page.locator('#poseMode').click();
  await page.locator('#setKey').click();assert.equal(await page.evaluate(()=>activeClip().keys[0].frame),0);
  await page.locator('#clipScrub').evaluate(e=>{e.value='12';e.dispatchEvent(new Event('input'))});
  const setup=await page.evaluate(()=>{boneState.pose.chest={angle:20};boneState.pose.hips={dx:10,dy:5};const [a,b,c]=ikChain('hand_l'),world=boneWorld(),m=world.get(a.name),end=world.get(c.name);return{start:{x:end[4],y:end[5]},target:{x:m[4]+Math.hypot(b.x-a.x,b.y-a.y)*.55,y:m[5]+Math.hypot(c.x-b.x,c.y-b.y)*.45},l1:Math.hypot(b.x-a.x,b.y-a.y),l2:Math.hypot(c.x-b.x,c.y-b.y)}});
  await page.evaluate(()=>render());
  async function drag(start,target){const box=await page.locator('#canvas').boundingBox(),z=await page.evaluate(()=>currentZoom());await page.mouse.move(box.x+start.x*z,box.y+start.y*z);await page.mouse.down();await page.mouse.move(box.x+target.x*z,box.y+target.y*z,{steps:5});await page.mouse.up()}
  await drag(setup.start,setup.target);
  async function geometry(){return page.evaluate(()=>{const chain=ikChain('hand_l'),world=boneWorld(),points=chain.map(b=>({x:world.get(b.name)[4],y:world.get(b.name)[5]}));return{points,bend:currentBend(chain,world),pose:boneState.pose}})}
  const result=await geometry(),[a,b,c]=result.points;assert(Math.hypot(c.x-setup.target.x,c.y-setup.target.y)<1e-4,JSON.stringify({setup,result,selected:await page.evaluate(()=>boneState.selected)}));assert(Math.abs(Math.hypot(b.x-a.x,b.y-a.y)-setup.l1)<1e-8);assert(Math.abs(Math.hypot(c.x-b.x,c.y-b.y)-setup.l2)<1e-8);
  const originalVertex=await page.evaluate(()=>meshFor(parts.find(p=>p.id==='arm_l')).vertices[50]);
  const movedVertex=await page.evaluate(()=>posedVertices(meshFor(parts.find(p=>p.id==='arm_l')),boneWorld())[50]);assert(Math.hypot(originalVertex.x-movedVertex.x,originalVertex.y-movedVertex.y)>1);
  await page.locator('#flipIK').click();const flipped=await geometry();assert.equal(flipped.bend,-result.bend);assert(Math.hypot(flipped.points[2].x-c.x,flipped.points[2].y-c.y)<1e-8);
  await page.keyboard.press('Control+z');assert.equal((await geometry()).bend,result.bend);
  await page.locator('#setKey').click();assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0,12]);
  await page.keyboard.press('Control+z');assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0]);
  await page.keyboard.press('Control+y');assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0,12]);
  await page.locator('#copyKey').click();await page.locator('#clipScrub').evaluate(e=>{e.value='24';e.dispatchEvent(new Event('input'))});await page.locator('#pasteKey').click();
  await page.locator('#moveKeyFrame').fill('20');await page.locator('#moveKey').click();assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0,12,20]);
  await page.locator('#moveKeyFrame').fill('24');await page.locator('#moveKey').click();assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0,12,24]);
  await page.locator('#newClip').click();assert.equal(await page.evaluate(()=>timelineState.config.clips.length),2);
  await page.locator('#removeClip').click();assert.equal(await page.evaluate(()=>timelineState.config.clips.length),1);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>timelineState.config.clips.length),2);
  await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>timelineState.config.clips.length),1);
  await page.locator('#rigMode').click();await page.locator('#boneSelect').selectOption('head');const restX=await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head').x);await page.locator('#boneX').fill(String(restX+2));await page.locator('#applyBonePoint').click();await page.locator('#poseMode').click();await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head').x),restX);await page.keyboard.press('Control+y');assert.equal(await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head').x),restX+2);
  await page.locator('#clipScrub').evaluate(e=>{e.value='6';e.dispatchEvent(new Event('input'))});assert.equal(await page.evaluate(()=>boneState.pose.chest.angle),10);
  await page.locator('#clipScrub').evaluate(e=>{e.value='30';e.dispatchEvent(new Event('input'))});await page.locator('#autoKey').check();await page.locator('#boneSelect').selectOption('head');await page.locator('#boneAngle').evaluate(e=>{e.value='15';e.dispatchEvent(new Event('input'));e.dispatchEvent(new Event('change'))});
  assert((await page.evaluate(()=>activeClip().keys.map(k=>k.frame))).includes(30));await page.locator('#autoKey').uncheck();await page.locator('#deleteKey').click();assert(!(await page.evaluate(()=>activeClip().keys.map(k=>k.frame))).includes(30));
  await page.locator('#undoKeys').click();assert((await page.evaluate(()=>activeClip().keys.map(k=>k.frame))).includes(30));await page.locator('#redoKeys').click();
  await page.locator('#clipFrames').fill('12');await page.locator('#applyClip').click();assert.equal(await page.evaluate(()=>activeClip().frames),48);
  await page.locator('#clipName').fill('손 흔들기');await page.locator('#clipFPS').fill('60');await page.locator('#clipFrames').fill('26');await page.locator('#clipLoop').uncheck();await page.locator('#applyClip').click();
  await page.locator('#clipStart').click();await page.locator('#playClip').click();await page.waitForFunction(()=>!timelineState.playing&&timelineState.frame===25);assert.equal(await page.evaluate(()=>timelineState.frame),25);
  await page.locator('#clipFrames').fill('48');await page.locator('#clipLoop').check();await page.locator('#applyClip').click();await page.locator('#clipScrub').evaluate(e=>{e.value='47';e.dispatchEvent(new Event('input'))});await page.locator('#playClip').click();await page.waitForFunction(()=>timelineState.playing&&timelineState.frame<20);await page.locator('#playClip').click();assert.equal(await page.evaluate(()=>timelineState.playing),false);
  await page.locator('#save').click();await page.waitForFunction(()=>!saving&&model.revision===1);assert.equal(saved.operations.filter(o=>o.kind==='rig_animation').length,1);assert.equal(await page.evaluate(()=>activeClip().name),'손 흔들기');assert.deepEqual(await page.evaluate(()=>activeClip().keys.map(k=>k.frame)),[0,12,24]);
  await page.reload();await page.waitForFunction(()=>boneState.rig&&activeClip());assert.equal(await page.evaluate(()=>activeClip().name),'손 흔들기');
  assert.deepEqual(errors,[]);console.log('Timeline browser passed: IK under rotated parents, lengths, bend flip, mesh motion, keys, undo, copy/paste, auto key, interpolation, loop/once playback, save/reload.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
