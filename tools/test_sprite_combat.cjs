/* Actual form scripts under a DOM mock; no browser rendering claim. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'web/index.html'),'utf8'),nodes={};
for(const match of html.matchAll(/<(input|select|textarea|div|p|button|a|span|video|img|section)[^>]*\bid="([^"]+)"[^>]*>/g)){
 const [tag,name,id]=match,handlers={};
 nodes[id]={tagName:name.toUpperCase(),type:tag.match(/type="([^"]+)"/)?.[1]||'',checked:tag.includes(' checked'),hidden:tag.includes(' hidden'),disabled:tag.includes(' disabled'),value:tag.match(/value="([^"]+)"/)?.[1]||'',style:{},options:[],previousElementSibling:{},
  addEventListener:(type,fn)=>{handlers[type]=fn},handlers,setAttribute(k,v){this[k]=v},reportValidity:()=>true,querySelector(){return {}},replaceChildren(){},};
 if(name==='select'){
  const content=html.slice(match.index+tag.length).split('</select>')[0];
  nodes[id].options=[...content.matchAll(/<option([^>]*)value="([^"]+)"([^>]*)>/g)].map(m=>({value:m[2],dataset:{},disabled:(m[1]+m[3]).includes('disabled'),selected:(m[1]+m[3]).includes('selected')}));
  nodes[id].value=(nodes[id].options.find(o=>o.selected)||nodes[id].options[0]).value;
  nodes[id].querySelector=selector=>nodes[id].options.find(o=>selector.includes('"'+o.value+'"'));
 }
}
let submitted;
const context=vm.createContext({console,document:{getElementById:id=>{assert(nodes[id],id);return nodes[id]},querySelector:()=>({})},MutationObserver:class{observe(){}},setInterval(){},setTimeout(){},confirm:()=>true,
 fetch:async(url,init)=>{if(url==='/api/status')return {json:async()=>({comfy:true,modelsReady:true,licenseConfirmed:true,spriteBackground:{ready:true}})};if(url==='/api/generate'){submitted=JSON.parse(init.body);return {ok:true,json:async()=>({jobId:'mock'})}};return {ok:true,json:async()=>({state:'cancelled'})}},});
context.window=context;
(async()=>{
 for(const script of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(script[1],context);
 vm.runInContext(fs.readFileSync(path.join(root,'web/assets/sprite-combat.js'),'utf8'),context);
 await new Promise(r=>setImmediate(r));
 assert.equal(context.spriteCombatPayload().combatEffect,'none');assert.equal(context.spriteCombatPayload().pixelOutput,false);
 nodes.applyChibiCombat.onclick();
 assert.equal(nodes.action.value,'attack');assert.equal(nodes.facing.value,'right');assert.equal(nodes.size.value,'768x640');assert.equal(nodes.motionPadding.value,'30');
 assert.equal(nodes.pixelExportFields.hidden,false);assert.equal(nodes.combatEffectFields.hidden,false);assert(nodes.pixelExportSize.textContent.includes('192×160'));
 assert.equal(nodes.backgroundRemoval.value,'flat');assert.equal(nodes.stabilize.checked,false);assert.equal(nodes.loop.checked,true);
 vm.runInContext("imageData='data:image/png;base64,test';sourceWidth=128;sourceHeight=128",context);
 await nodes.generate.onclick();
 assert(submitted);assert.equal(submitted.combatEffect,'blue_slash');assert.equal(submitted.pixelOutput,true);assert.equal(submitted.pixelColorLock,true);assert.equal(submitted.frameCount,30);assert.equal(submitted.width,768);assert.equal(submitted.height,640);assert.equal(submitted.samplingMode,'quality');assert(submitted.prompt.includes('ONE clear sword attack'));
 context.applyRecreatePreset(submitted);assert.equal(nodes.pixelOutput.checked,true);assert.equal(nodes.combatEffect.value,'blue_slash');
 context.applyRecreatePreset({animationType:'idle',width:512,height:512});assert.equal(nodes.pixelOutput.checked,false);assert.equal(nodes.combatEffect.value,'none');assert.equal(nodes.combatEffectFields.hidden,true);
 context.applyRecreatePreset({animationType:'attack',loop:false,motionSpeed:2,trimAction:true,width:512,height:512});assert.equal(nodes.motionSpeed.value,'2');assert.equal(nodes.trimAction.checked,true);assert.equal(nodes.trimAction.disabled,false);await nodes.generate.onclick();assert.equal(submitted.motionSpeed,2);assert.equal(submitted.trimAction,true);nodes.applyChibiCombat.onclick();assert.equal(nodes.motionSpeed.value,'1');assert.equal(nodes.trimAction.checked,false);assert.equal(nodes.trimAction.disabled,true);
 nodes.combatEffect.value='custom';context.spriteCombatControls();assert.equal(nodes.effectDescription.required,true);assert.equal(nodes.effectDescription['aria-required'],'true');
 console.log('PASS actual form payload, native quality recipe, effect/pixel UI, exact dimensions, saved-setting restore, legacy reset, required custom text (DOM mock)');
})().catch(e=>{console.error(e);process.exitCode=1});
