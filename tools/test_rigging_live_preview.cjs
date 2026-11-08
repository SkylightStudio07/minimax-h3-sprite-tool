/* Real player + real layered fixture; all editing stays in browser memory. */
const {chromium}=require('playwright'),{execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import json,base64
from pathlib import Path
import rigging_editor as editor,rigging_bones
folder=Path('outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df')
m=editor.read_manifest(folder);records=dict(editor.layer_records(m));layers=[];images={}
for key in editor.effective_layer_order(m):
 p=dict(records[key]);p.update(key=key,kind='part' if key.startswith('part:') else 'expression',asset='/fixture/'+key,originalAsset='/fixture/'+key)
 p['defaultVisible']=key.startswith('part:') or p.get('fade')=='eyeOpen' or p['id']=='eyebrow' or p['id']=='mouth_close'
 layers.append(p);images[key]=base64.b64encode(editor.layer_bytes(folder,p['id'],kind=p['kind'])).decode()
print(json.dumps(dict(model=dict(canvas=m['canvas'],revision=0,layers=layers,rig=rigging_bones.get_rig(m),versions=[]),images=images)))
`],{cwd:root,encoding:'utf8',maxBuffer:20*1024*1024}));
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];let posts=0,psdDownloads=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://rig.test/**',async route=>{
   const u=new URL(route.request().url()),name=u.pathname;
   if(route.request().method()==='POST'){posts++;return route.fulfill({status:500,body:'Preview must not save'})}
   if(name.endsWith('character.psd')){psdDownloads++;return route.fulfill({status:404})}
   if(name==='/rigging-editor'||name.endsWith('/inspector'))return route.fulfill({path:path.join(root,'web/rigging-editor.html')});
   if(name.startsWith('/assets/')||/^\/rigging-[^/]+\.js$/.test(name))return route.fulfill({path:path.join(root,'web',name)});
   if(name==='/share/rig/internal/player'){
    const html=fs.readFileSync(path.join(root,'vendor/Anime2.5DRig/index.html'),'utf8').replace('<head>','<head><base href="/shared-rig-player/">').replace('<script src="lib/app.js">','<script>window.SHARED_MODEL_URL="/share/rig/internal/asset/character.psd"</script><script src="lib/app.js">');return route.fulfill({contentType:'text/html',body:html});
   }
   if(name.startsWith('/rigging-player/')||name.startsWith('/shared-rig-player/')){const rel=name.replace(/^\/(?:rigging-player|shared-rig-player)\//,'');const file=path.join(root,'vendor/Anime2.5DRig',rel);return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404})}
   if(name.startsWith('/fixture/'))return route.fulfill({contentType:'image/png',body:Buffer.from(fixture.images[decodeURIComponent(name.slice(9))],'base64')});
   if(name.endsWith('/rig-edit'))return route.fulfill({json:fixture.model});
   return route.fulfill({status:404});
  });
  await page.goto('http://rig.test/rigging-editor?job=test');await page.waitForFunction(()=>parts.length>10&&boneState.rig);
  assert.equal(await page.locator('#livePreviewPlayer').count(),0);
  const canvasBefore=await page.evaluate(()=>canvas.toDataURL());
  await page.locator('#toggleLivePreview').click();await page.waitForFunction(()=>document.querySelector('#livePreviewPanel').dataset.state==='ready',null,{timeout:45000});
  const player=()=>page.frames().find(f=>f.url().includes('editor=1'));
  assert((await player().evaluate(()=>window.spriteEditorPreview.state())).layers.length>5);
  const moving1=await player().locator('#cv').screenshot();await page.waitForTimeout(250);const moving2=await player().locator('#cv').screenshot();assert(!moving1.equals(moving2),'real runtime must animate');
  assert.equal(await page.evaluate(()=>canvas.toDataURL()),canvasBefore,'opening player must not alter editor canvas');
  const updates=await player().evaluate(()=>window.spriteEditorPreview.state().updates);
  await page.locator('[data-layer-key="part:back_hair"] input').uncheck();
  await page.waitForFunction(n=>document.querySelector('#livePreviewPlayer').contentWindow.spriteEditorPreview.state().updates>n,updates);
  assert(!(await player().evaluate(()=>window.spriteEditorPreview.state().layers)).some(p=>p.name==='back hair'));
  assert((await page.locator('#livePreviewStatus').textContent()).includes('저장 전'));
  assert.equal(await page.evaluate(()=>history.length),1);
  const next=await player().evaluate(()=>window.spriteEditorPreview.state().updates);await page.locator('#undo').click();
  await page.waitForFunction(n=>document.querySelector('#livePreviewPlayer').contentWindow.spriteEditorPreview.state().updates>n,next);
  assert((await player().evaluate(()=>window.spriteEditorPreview.state().layers)).some(p=>p.name==='back hair'));
  await page.locator('#pauseLivePreview').click();assert.equal(await player().evaluate(()=>window.spriteEditorPreview.state().paused),true);
  // Observe the real runtime input, then erase pixels through the actual pointer tool.
  await player().evaluate(()=>{const api=window.spriteEditorPreview,load=api.load;window.previewSnapshots=[];api.load=async function(psd){window.previewSnapshots.push(psd);return load.call(this,psd)}});
  await page.locator('#refreshLivePreview').click();await page.waitForFunction(()=>document.querySelector('#livePreviewPanel').dataset.state==='ready');
  const hairAlpha=()=>player().evaluate(()=>{const p=window.previewSnapshots.at(-1).children.find(p=>p.name==='front hair');let sum=0;for(let i=3;i<p.imageData.data.length;i+=4)sum+=p.imageData.data[i];return sum});
  const originalAlpha=await hairAlpha();
  await page.locator('[data-layer-key="part:front_hair"]').click();
  const point=await page.evaluate(()=>{setTool('erase');$('size').value='32';const p=selected,d=p.canvas.getContext('2d').getImageData(0,0,p.width,p.height).data;let best=Infinity,x=0,y=0;for(let j=0;j<p.height;j++)for(let i=0;i<p.width;i++){const distance=(i-p.width/2)**2+(j-p.height/2)**2;if(d[(j*p.width+i)*4+3]>200&&distance<best){best=distance;x=i;y=j}}const r=canvas.getBoundingClientRect();return{x:r.x+(p.left+x)*r.width/canvas.width,y:r.y+(p.top+y)*r.height/canvas.height}});
  const erasedUpdate=await player().evaluate(()=>window.spriteEditorPreview.state().updates);
  await page.mouse.click(point.x,point.y);
  await page.waitForFunction(n=>document.querySelector('#livePreviewPlayer').contentWindow.spriteEditorPreview.state().updates>n,erasedUpdate);
  assert(await hairAlpha()<originalAlpha,'unsaved erased pixels must reach the actual player');
  const undoUpdate=await player().evaluate(()=>window.spriteEditorPreview.state().updates);await page.locator('#undo').click();
  await page.waitForFunction(n=>document.querySelector('#livePreviewPlayer').contentWindow.spriteEditorPreview.state().updates>n,undoUpdate);
  assert.equal(await hairAlpha(),originalAlpha);
  await page.screenshot({path:path.join(root,'outputs/rigging-live-preview-desktop.png'),fullPage:true});
  await page.locator('#closeLivePreview').click();assert.equal(await page.locator('#livePreviewPlayer').count(),0);assert.equal(await page.locator('#toggleLivePreview').getAttribute('aria-expanded'),'false');
  await page.setViewportSize({width:390,height:844});
  await page.goto('http://rig.test/share/rig/internal/inspector');await page.waitForFunction(()=>parts.length>10);
  await page.locator('#toggleLivePreview').click();await page.waitForFunction(()=>document.querySelector('#livePreviewPanel').dataset.state==='ready',null,{timeout:45000});
  assert.equal(psdDownloads,0,'editor preview must not fetch the saved PSD or trigger downloads');
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert(await page.locator('#livePreviewPlayer').isVisible());
  assert((await page.locator('#livePreviewPlayer').boundingBox()).height>=140);
  const playerSize=await player().evaluate(()=>({height:innerHeight,stage:document.getElementById('stage').clientHeight,canvas:document.getElementById('cv').getBoundingClientRect().height}));
  assert(playerSize.stage<=playerSize.height+1&&playerSize.canvas<=playerSize.height+1,'small preview must fit the full character');
  await page.screenshot({path:path.join(root,'outputs/rigging-live-preview-mobile.png'),fullPage:true});
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log('PASS: real live animation, unsaved eraser pixels/visibility + undo sync, unchanged editor pixels, pause, teardown, internal share without PSD downloads, mobile, no server writes.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
