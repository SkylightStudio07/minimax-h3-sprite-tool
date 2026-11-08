// Native browser regression against isolated fixture APIs. No production edits.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import rigging_bones as bones, io, base64, json
from PIL import Image
manifest={'canvas':{'width':256,'height':384},'parts':[
 {'id':'body','runtimeName':'body','left':20,'top':10,'width':210,'height':360},
 {'id':'hair','runtimeName':'hair','left':80,'top':20,'width':100,'height':120}],'expressions':[]}
images={}
for name,color in [('body',(30,40,90,255)),('hair',(15,200,90,255))]:
 out=io.BytesIO();Image.new('RGBA',(8,8),color).save(out,'PNG');images[name]=base64.b64encode(out.getvalue()).decode()
rig=bones.get_rig(manifest)
print(json.dumps({'rig':rig,'parts':manifest['parts'],'images':images,'meshes':bones.layer_meshes(manifest,rig)}))
`],{cwd:root,encoding:'utf8'}));
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1550,height:1080},deviceScaleFactor:1}),errors=[];let revision=0,saved=null,v2Endpoint=null,rig=structuredClone(fixture.rig);
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/rigging-editor'||url.pathname.endsWith('/inspector'))return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'web/rigging-editor.html'),'utf8')});
   if(url.pathname.startsWith('/assets/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':url.pathname.endsWith('.js')?'text/javascript':'font/woff2',body:fs.readFileSync(path.join(root,'web',url.pathname))});
   if(['/rigging-expressions.js','/rigging-bones.js','/rigging-animation.js','/rigging-animation-math.js'].includes(url.pathname))return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'web',path.basename(url.pathname)),'utf8')});
   if(url.pathname.startsWith('/fixture/'))return route.fulfill({contentType:'image/png',body:Buffer.from(fixture.images[path.basename(url.pathname,'.png')],'base64')});
   if(url.pathname.endsWith('/revisions')){saved=route.request().postDataJSON();revision++;rig=saved.operations.filter(op=>op.kind==='rig_config').at(-1).config;return route.fulfill({json:{revision}})}
   if(url.pathname.endsWith('/rig-v2')){v2Endpoint=url.pathname;return route.fulfill({json:{packageV2:'/fixture-v2.zip',boneCount:rig.bones.length}})}
   if(url.pathname.endsWith('/rig-edit'))return route.fulfill({json:{canvas:{width:256,height:384},revision,rig,layers:fixture.parts.map(p=>({...p,key:'part:'+p.id,kind:'part',defaultVisible:true,asset:'/fixture/'+p.id+'.png',originalAsset:'/fixture/'+p.id+'.png'})),versions:[]}});
   return route.fulfill({status:404,body:'Not mocked'});
  });
  await page.goto('http://sprite.test/rigging-editor?job=test');await page.waitForFunction(()=>boneState.rig);
  // Studio UI: icon tool rail, layer thumbnails, Photoshop-style brush cursor (assets/editor-ui.js).
  assert.equal(await page.locator('.tools .tool svg').count(),5,'every tool, including the paint tool, shows an icon');
  assert.equal(await page.locator('#layers .layer-thumb').count(),await page.locator('#layers .layer').count(),'each layer row has a thumbnail');
  await page.locator('[data-layer-key="part:hair"]').click();await page.keyboard.press('e');
  const canvasBox=await page.locator('#canvas').boundingBox();
  await page.mouse.move(canvasBox.x+canvasBox.width/2,canvasBox.y+canvasBox.height/2);
  const cursorSize=()=>page.locator('.brush-cursor').evaluate(el=>el.hidden?0:parseFloat(el.style.width));
  const brushPx=Number(await page.locator('#size').inputValue()),expectedRing=Math.max(4,brushPx*canvasBox.width/256);
  assert(Math.abs(await cursorSize()-expectedRing)<1,`cursor diameter follows brush size × zoom (${await cursorSize()} vs ${expectedRing})`);
  assert.equal(await page.evaluate(()=>getComputedStyle(document.getElementById('canvas')).cursor),'none','native cursor hidden under the ring');
  await page.keyboard.press(']');await page.waitForTimeout(50);
  assert(await cursorSize()>expectedRing,'] grows the ring');
  assert.equal(await page.locator('.brush-size-tag.is-on').count(),1,'size flashes next to the cursor');
  await page.keyboard.down('Alt');await page.waitForTimeout(50);assert.equal(await cursorSize(),0,'Alt (temporary select) hides the ring');await page.keyboard.up('Alt');
  await page.keyboard.press('v');await page.waitForTimeout(50);
  assert.equal(await cursorSize(),0,'selection tool has no brush ring');
  await page.keyboard.press('[');
  // Browser and exporter must derive identical weights and rest vertices.
  const meshes=await page.evaluate(()=>parts.map(part=>{const mesh=meshFor(part);return{layerKey:part.key,vertices:mesh.vertices.map(v=>({x:v.x,y:v.y,boneIndices:v.weights.map(w=>w.i),weights:v.weights.map(w=>w.w)})),indices:mesh.indices}}));
  for(let m=0;m<meshes.length;m++)for(let i=0;i<81;i++){const actual=meshes[m].vertices[i],expected=fixture.meshes[m].vertices[i];assert.deepEqual(actual.boneIndices,expected.boneIndices);actual.weights.forEach((w,j)=>assert(Math.abs(w-expected.weights[j])<1e-12));assert.equal(actual.x,expected.x);assert.equal(actual.y,expected.y)}
  await page.locator('#rigMode').click();
  const restBefore=await page.evaluate(()=>({...boneState.rig.bones.find(b=>b.name==='head')}));
  const pixelBefore=await page.evaluate(()=>Array.from(ctx.getImageData(86,32,1,1).data));
  assert.deepEqual(pixelBefore,[15,200,90,255]);
  async function drag(x,y,dx,dy){const box=await page.locator('#canvas').boundingBox(),zoom=await page.evaluate(()=>currentZoom());await page.mouse.move(box.x+x*zoom,box.y+y*zoom);await page.mouse.down();await page.mouse.move(box.x+(x+dx)*zoom,box.y+(y+dy)*zoom,{steps:4});await page.mouse.up()}
  await drag(restBefore.x,restBefore.y,20,0);
  assert.equal(await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head').x),restBefore.x+20);
  assert.deepEqual(await page.evaluate(()=>Array.from(ctx.getImageData(86,32,1,1).data)),pixelBefore);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head').x),restBefore.x);
  await page.keyboard.press('Control+y');
  await page.locator('[data-layer-key="part:hair"]').click();await page.locator('#addBoneControl').click();
  assert.equal(await page.evaluate(()=>boneState.rig.bones.length),21);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>boneState.rig.bones.length),19);
  await page.keyboard.press('Control+y');
  await page.locator('#boneSelect').selectOption('control_1');await page.locator('#removeBone').click();assert.equal(await page.evaluate(()=>boneState.rig.bones.length),19);
  await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>boneState.rig.bones.length),21);
  await page.locator('#poseMode').click();await page.locator('#boneSelect').selectOption('head');
  const head=await page.evaluate(()=>boneState.rig.bones.find(b=>b.name==='head'));
  await drag(head.x,head.y,30,0);
  assert.equal(await page.evaluate(()=>boneState.pose.head.dx),30);
  assert.deepEqual(await page.evaluate(()=>Array.from(ctx.getImageData(86,32,1,1).data)),[30,40,90,255]);
  const posed=await page.evaluate(()=>{const mesh=meshFor(parts.find(p=>p.id==='hair'));return posedVertices(mesh,boneWorld())[0].x});
  assert(Math.abs(posed-110)<1e-9);
  await page.locator('#poseUndo').click();assert.equal(await page.evaluate(()=>Object.keys(boneState.pose).length),0);
  await page.locator('#poseRedo').click();
  await page.locator('#boneAngle').evaluate(input=>{input.value='20';input.dispatchEvent(new Event('input'));input.dispatchEvent(new Event('change'))});
  assert.equal(await page.evaluate(()=>boneState.pose.head.angle),20);
  await page.locator('#resetPose').click();assert.equal(await page.evaluate(()=>Object.keys(boneState.pose).length),0);
  await page.locator('#save').click();await page.waitForFunction(()=>!saving&&model.revision===1);
  assert(saved.operations.every(op=>op.kind==='rig_config'));assert(!JSON.stringify(saved).includes('dx'));assert(!JSON.stringify(saved).includes('before'));
  assert.equal(await page.evaluate(()=>boneState.rig.bones.length),21);
  await page.locator('#boneV2').click();await page.waitForFunction(()=>!saving);assert.equal(v2Endpoint,'/api/jobs/test/rig-v2');
  // Result-page deep links open the editor straight into a mode.
  for(const [mode,expected] of [['bones','rest'],['animation','pose']]){await page.goto(`http://sprite.test/rigging-editor?job=test&mode=${mode}`);await page.waitForFunction(m=>boneState.rig&&boneState.mode===m,expected);}
  await page.goto('http://sprite.test/rigging-editor?job=test&mode=animation');await page.waitForFunction(()=>boneState.mode==='pose');assert.equal(await page.locator('.rig-timeline').isVisible(),true,'animation deep link shows the timeline');
  await page.goto('http://sprite.test/share/rig/token/inspector');await page.waitForFunction(()=>boneState.rig);await page.locator('#boneV2').click();await page.waitForFunction(()=>!saving);assert.equal(v2Endpoint,'/share/rig/token/rig-v2');
  assert.deepEqual(errors,[]);
  console.log('Bone browser flow passed: shared weights, rest drag, unchanged pixels, controls, pose skinning, undo, rotation, save, V2, internal share, mode deep links.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
