"""CPU-only palette ramp merging + bidirectional colour consensus; alpha unchanged."""
import hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sprite_gif
from tools import export_pixel_sword_combo as ep
SOURCE=ROOT/'outputs/pixel-spin-step-turn-20261019/spin_slash'
OUT=ROOT/'outputs/pixel-color-lock-20261019'
# Manually reviewed palette ramp merge for THIS auburn/teal/cream character.
# Keep skin, cream, silver and the four FX colours distinct.
MERGE=np.array([0,1,1,3,4,4,3,1,1,4,10,10,12,12,14,12,16,17,18,14,17,17,18,23,24,23,26,26,29,29,30,31,32,33,34,35],np.uint8)
FAMILY=np.array([0]*10+[1,1,1,1,1,1,2,1,1,1,1,1,1,1,2,1,3,3,4,4,3,5,6,6,6,6],np.uint8)
METHODS={'original':'기존 · 36색','palette':'비슷한 색 묶기 · 20색','stable':'색 묶기 + 움직임에 맞춰 유지'}
OPTIONS={
 'original':dict(label='원본색 · 기본',description='기존 색과 명암을 그대로 저장합니다.',paletteLimit=36),
 'palette':dict(label='비슷한 색 묶기',description='비슷한 명암색을 묶습니다. 색 변화가 줄지만 작은 명암도 단순해집니다.',paletteLimit=20),
 'stable':dict(label='색 흔들림 줄이기',description='색을 묶고, 움직임이 확실한 같은 부위의 색을 앞뒤 프레임에 맞춰 유지합니다.',paletteLimit=20),
}

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def consensus(labels,arrays,grays,palette):
 out=[];records=[]
 depths=[cv2.distanceTransform((a[:,:,3]>0).astype(np.uint8),cv2.DIST_L2,3) for a in arrays]
 colours=np.unique(MERGE)
 for i,current in enumerate(labels):
  scores=np.zeros((192,192,len(palette)),np.float32)
  np.put_along_axis(scores,current[:,:,None],1.25,axis=2)
  total=np.zeros((192,192),np.uint8)
  for j in range(max(0,i-2),min(len(labels),i+3)):
   if i==j:continue
   mx,my,valid=ep.flow_pair(grays[j],grays[i])
   old=cv2.remap(labels[j],mx,my,cv2.INTER_NEAREST)
   depth=cv2.remap(depths[j],mx,my,cv2.INTER_NEAREST)
   photo=cv2.remap(grays[j],mx,my,cv2.INTER_LINEAR)
   distance=np.sum((palette[old].astype(float)-palette[current].astype(float))**2,axis=2)
   valid&=(depths[i]>1.5)&(depth>1.5)&(FAMILY[current]==FAMILY[old])&(FAMILY[current]<5)&(distance<1800)&(np.abs(grays[i].astype(float)-photo)<18)
   total+=valid
   for c in colours:scores[:,:,c]+=valid&(old==c)
  chosen=scores.argmax(axis=2).astype(np.uint8);a=arrays[i].copy();a[:,:,:3]=palette[chosen];a[a[:,:,3]==0,:3]=0
  assert np.array_equal(a[:,:,3],arrays[i][:,:,3])
  out.append(a);records.append(dict(frame=i,changedPixels=int(np.any(a!=arrays[i],axis=2).sum()),pixelsWithTwoOrMoreValidNeighbours=int((total>=2).sum())))
 return out,records

def metrics(original,merged,stable,grays):
 # Same geometry/flow mask for every method; only compare near-static holds.
 records=[]
 for start,end in [(40,55),(64,72)]:
  totals={m:dict(samples=0,rgbDistanceSum=0.,changed=0) for m in METHODS}
  for i in range(start+1,end+1):
   mx,my,valid=ep.flow_pair(grays[i-1],grays[i]);valid&=(original[i][:,:,3]>0)&(cv2.remap(original[i-1][:,:,3],mx,my,cv2.INTER_NEAREST)>0)
   valid&=cv2.distanceTransform((original[i][:,:,3]>0).astype(np.uint8),cv2.DIST_L2,3)>1.5
   # No sword, halo, or newly revealed material in this colour stability proxy.
   pal=np.array(json.loads((SOURCE/'source-settings.json').read_text(encoding='utf-8'))['palette'],np.uint8)
   labels=((original[i][:,:,:3,None].transpose(0,1,3,2).astype(float)-pal[None,None])**2).sum(axis=3).argmin(axis=2)
   valid&=FAMILY[labels]<5
   for name,frames in zip(METHODS,[original,merged,stable]):
    old=cv2.remap(frames[i-1][:,:,:3],mx,my,cv2.INTER_NEAREST);diff=frames[i][:,:,:3].astype(float)-old
    totals[name]['samples']+=int(valid.sum());totals[name]['changed']+=int((np.any(diff!=0,axis=2)&valid).sum());totals[name]['rgbDistanceSum']+=float(np.linalg.norm(diff,axis=2)[valid].sum())
  records.append(dict(sourceRange=[start,end],methods={m:dict(samples=v['samples'],changedRatio=round(v['changed']/max(v['samples'],1),4),meanRGBDistance=round(v['rgbDistanceSum']/max(v['samples'],1),3)) for m,v in totals.items()}))
 return records

SCRIPT=r'''
const cfg=JSON.parse(document.getElementById('configs').textContent),pictures=document.querySelectorAll('img[data-method]');
for(const pic of pictures)for(let i=0;i<cfg.indices.length;i++){const im=new Image();im.src=pic.dataset.method+'/frame-'+String(i).padStart(2,'0')+'.png'}
let index=0,playing=true,last=performance.now(),elapsed=0;
const get=id=>document.getElementById(id);
const choice=get('colorMode'),compare=get('compare'),cards=document.querySelectorAll('[data-color-choice]');
function choose(){
 if(!Object.hasOwn(cfg.options,choice.value))choice.value='original';
 const mode=choice.value,option=cfg.options[mode];
 for(const card of cards){card.hidden=!compare.checked&&card.dataset.colorChoice!==mode;card.classList.toggle('selected',card.dataset.colorChoice===mode)}
 get('colorDescription').textContent=option.description;
 for(const [id,file,ext] of [['saveSheet','sheet-grid.png','png'],['saveAnimation','animation.png','png'],['saveGif','animation.gif','gif'],['saveBundle','assets.zip','zip']]){
  get(id).href=mode+'/'+file;get(id).download='pixel-'+mode+(ext==='zip'?'':id==='saveSheet'?'-sheet':'-animation')+'.'+ext;
 }
 try{localStorage.setItem('pixel-color-mode-v1',mode)}catch{}
}
try{const saved=localStorage.getItem('pixel-color-mode-v1');if(Object.hasOwn(cfg.options,saved))choice.value=saved}catch{}
choice.onchange=choose;compare.onchange=choose;choose();
function draw(){for(const pic of pictures)pic.src=pic.dataset.method+'/frame-'+String(index).padStart(2,'0')+'.png';get('slider').value=index;get('phase').textContent=(index+1)+' / '+cfg.indices.length+' · 원본 '+cfg.indices[index]+'번';get('play').textContent=playing?'일시 정지':'재생'}
function step(d){playing=false;elapsed=0;index=(index+d+cfg.indices.length)%cfg.indices.length;draw()}
get('play').onclick=()=>{playing=!playing;elapsed=0;last=performance.now();draw()};get('previous').onclick=()=>step(-1);get('next').onclick=()=>step(1);
get('slider').oninput=()=>{playing=false;elapsed=0;index=Number(get('slider').value);draw()};
get('zoom').onchange=e=>document.documentElement.style.setProperty('--scale',e.target.value);
get('background').onchange=e=>document.body.dataset.background=e.target.value;
function tick(now){const dt=Math.max(0,Math.min(now-last,200));last=now;if(playing){elapsed+=dt*Number(get('speed').value);let changed=false;while(elapsed>=cfg.durations[index]){elapsed-=cfg.durations[index];index=(index+1)%cfg.indices.length;changed=true}if(changed)draw()}requestAnimationFrame(tick)}draw();requestAnimationFrame(tick);
'''

def build():
 meta=json.loads((OUT/'stable/frames.json').read_text(encoding='utf-8'));n=len(meta['sourceIndices'])
 cards=''.join(f'<article data-color-choice="{key}"><h2>{OPTIONS[key]["label"]}</h2><img data-method="{key}" src="{key}/frame-00.png"><p><a href="{key}/sheet-grid.png">PNG 시트</a> · <a href="{key}/animation.webp">애니메이션</a></p></article>' for key in METHODS)
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>캐릭터 색 흔들림 비교</title><style>:root{--scale:2}body{font:15px/1.6 system-ui;background:#151b26;color:#eee;margin:24px auto;max-width:1400px;padding:0 20px}a{color:#cbc5ff}h1{font-size:26px}h2{font-size:16px}.cards{display:flex;flex-wrap:wrap;gap:16px}article{background:#252d3b;padding:12px;border-radius:10px;overflow:auto}img{display:block;width:calc(192px * var(--scale));height:calc(192px * var(--scale));max-width:none;image-rendering:pixelated;background:#202632}body[data-background=light] img{background:#eee}body[data-background=checker] img{background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0}button,select{background:#323f58;color:#fff;border:1px solid #64728c;border-radius:6px;padding:8px}input{min-width:200px;flex:1}.notice{background:#29394b;padding:12px;border-radius:8px}</style><h1>캐릭터 색 흔들림 비교</h1><p>같은 동작·같은 프레임을 함께 재생합니다. 가운데는 비슷한 명암색을 묶고, 오른쪽은 움직임이 확실한 같은 부위에서 앞뒤 프레임의 색도 참고합니다.</p><p class="notice">윤곽과 투명도는 세 버전이 정확히 같습니다. 색을 묶으면 작은 명암 차이는 줄어듭니다. 크게 돌아 새로 드러나는 부위의 색이나 생성된 옷 형태까지 완전히 고정하는 기능은 아닙니다.</p><p><a href="pixel-color-lock.zip" download>비교·프레임·시트 ZIP</a> · <a href="results.json">처리 기록</a></p><div class="controls"><button id="play">일시 정지</button><button id="previous" aria-label="이전 프레임">←</button><button id="next" aria-label="다음 프레임">→</button><input id="slider" type="range" min="0" max="COUNT" value="0" aria-label="프레임 선택"><span id="phase"></span><label>속도 <select id="speed"><option value="0.5">0.5배</option><option selected value="1">1배</option><option value="2">2배</option></select></label><label>배율 <select id="zoom"><option value="1">1배</option><option value="2" selected>2배</option><option value="3">3배</option></select></label><label>배경 <select id="background"><option value="dark">어둡게</option><option value="light">밝게</option><option value="checker">체커보드</option></select></label></div><div class="cards">'''.replace('COUNT',str(n-1))+cards+'</div><script id="configs" type="application/json">'+json.dumps(dict(indices=meta['sourceIndices'],durations=meta['durationMs']))+'</script><script>'+SCRIPT+'</script></html>'
 # Add the optional export choice to the existing synchronized review controls.
 config=dict(indices=meta['sourceIndices'],durations=meta['durationMs'],options=OPTIONS,defaultMode='original')
 page=re.sub(r'(<script id="configs" type="application/json">).*?(</script>)',lambda m:m[1]+json.dumps(config,ensure_ascii=False)+m[2],page,flags=re.S)
 page=page.replace('</style>','article.selected{outline:2px solid #aebaff}article[hidden]{display:none}.option-controls{background:#252d3b;padding:14px;border-radius:10px}.option-controls input[type=checkbox]{min-width:0;flex:none}a.download{display:inline-block;padding:8px 12px;border:1px solid #64728c;border-radius:6px}</style>')
 selector=''.join(f'<option value="{key}"'+(' selected' if key=='original' else '')+'>'+value['label']+'</option>' for key,value in OPTIONS.items())
 controls='<div class="option-controls"><label for="colorMode">色OPTION</label><select id="colorMode">'+selector+'</select> <label><input id="compare" type="checkbox"> 세 버전 함께 비교</label><p id="colorDescription" role="status"></p><p><a id="saveSheet" class="download" href="original/sheet-grid.png" download>선택한 PNG 시트 저장</a> <a id="saveAnimation" class="download" href="original/animation.png" download>선택한 애니메이션 저장</a> <a id="saveBundle" class="download" href="original/assets.zip" download>선택한 버전 전체 ZIP</a></p></div>'
 page=page.replace('<div class="controls"><button id="play">',controls.replace('色OPTION','색상 처리 · 선택 사항')+'<div class="controls"><button id="play">',1)
 page=page.replace('<a id="saveBundle"','<a id="saveGif" class="download" href="original/animation.gif" download>선택한 GIF 저장 · 인계용</a> <a id="saveBundle"',1)
 page=page.replace('같은 동작·같은 프레임을 함께 재생합니다. 가운데는 비슷한 명암색을 묶고, 오른쪽은 움직임이 확실한 같은 부위에서 앞뒤 프레임의 색도 참고합니다.','원본색이 기본입니다. 필요할 때 색상 처리를 선택하고 해당 버전을 저장하세요. 함께 비교를 켜면 같은 동작·같은 프레임으로 차이를 확인할 수 있습니다.')
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script-check.js').write_text(SCRIPT,encoding='utf-8')
 save(OUT/'options.json',dict(defaultMode='original',options=OPTIONS,status='accepted as optional by user',scope='Current pixel animation review/export; manual colour profile for the reviewed swordswoman'))
 for key in METHODS:
  folder=OUT/key;frames=json.loads((folder/'frames.json').read_text(encoding='utf-8'));frames['colorProcessing']=dict(mode=key,**OPTIONS[key],profile='auburn-teal-cream-v1')
  images=[]
  for i in range(len(frames['sourceIndices'])):
   with Image.open(folder/f'frame-{i:02d}.png') as image:images.append(image.convert('RGBA'))
  gif,gif_info=sprite_gif.encode(images,frames['durationMs']);(folder/'animation.gif').write_bytes(gif);save(folder/'gif.json',gif_info)
  save(folder/'frames.json',frames)
  save(folder/'color-settings.json',dict(mode=key,**OPTIONS[key],defaultMode='original',profile='auburn-teal-cream-v1',source=str(SOURCE),geometryAndAlphaUnchanged=True))
  with zipfile.ZipFile(folder/'assets.zip','w',zipfile.ZIP_DEFLATED) as z:
   for p in folder.rglob('*'):
    if p.is_file() and p.suffix in ('.png','.webp','.gif','.json'):z.write(p,p.relative_to(folder))
 results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));results.update(status='accepted as optional; original remains default',defaultColorMode='original');save(OUT/'results.json',results)

def process():
 cv2.setNumThreads(4);OUT.mkdir(exist_ok=True)
 pal=np.array(json.loads((SOURCE/'source-settings.json').read_text(encoding='utf-8'))['palette'],np.uint8)
 originals=[np.array(Image.open(p).convert('RGBA')) for p in sorted((SOURCE/'all-frames').glob('frame-*.png'))]
 lut={tuple(c):i for i,c in enumerate(pal)};labels=[];merged=[];grays=[]
 for a in originals:
  l=np.zeros((192,192),np.uint8)
  for c,index in lut.items():l[np.all(a[:,:,:3]==c,axis=2)]=index
  l=MERGE[l];labels.append(l);b=a.copy();b[:,:,:3]=pal[l];b[b[:,:,3]==0,:3]=0;merged.append(b)
  composite=a[:,:,:3].copy();composite[a[:,:,3]==0]=32;grays.append(cv2.cvtColor(composite,cv2.COLOR_RGB2GRAY))
 stable,records=consensus(labels,merged,grays,pal)
 for name,frames in zip(METHODS,[originals,merged,stable]):
  folder=OUT/name;(folder/'all-frames').mkdir(parents=True,exist_ok=True)
  shutil.copyfile(SOURCE/'selection.json',folder/'selection.json')
  save(folder/'postprocess.json',dict(frames=len(frames)))
  for i,a in enumerate(frames):
   assert np.array_equal(a[:,:,3],originals[i][:,:,3]);Image.fromarray(a).save(folder/'all-frames'/f'frame-{i:03d}.png')
  ep.OUT=folder;ep.WIDTH=ep.HEIGHT=192;ep.selected()
 review_indices=[0,8,20,26,34,50,64,72];sheet=Image.new('RGB',(3*384,8*408),'#202632');draw=ImageDraw.Draw(sheet)
 for row,i in enumerate(review_indices):
  for col,frames in enumerate([originals,merged,stable]):
   im=Image.fromarray(frames[i]).resize((384,384),Image.Resampling.NEAREST);sheet.paste(im,(col*384,row*408+24),im);draw.text((col*384+5,row*408+4),f'{list(METHODS)[col]} source {i}',fill='white')
 sheet.save(OUT/'comparison.png')
 results=dict(status='experimental; user review pending',source=str(SOURCE),sourceHashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'action-raw.mp4',SOURCE/'sheet-grid.png',SOURCE/'reference.png']},palette=pal.tolist(),merge=MERGE.tolist(),mergedPaletteSize=len(np.unique(MERGE)),frameCount=len(originals),alphaAndGeometryUnchanged=True,temporalWindow=5,changed=records,holdStabilityProxy=metrics(originals,merged,stable,grays),limitations=['Manual palette ramps apply only to this auburn/cream/teal character.','Same-material, confident motion only; new surfaces/occlusions are not forced to old colours.','No correction of outfit/weapon shape, clipped sword, or material identity swaps.','Reduced ramps lose subtle shading; proxy metrics are not visual quality scores.'])
 save(OUT/'results.json',results);build();print(json.dumps(dict(paletteSize=results['mergedPaletteSize'],changed=sum(r['changedPixels'] for r in records),holds=results['holdStabilityProxy']),ensure_ascii=False),flush=True)

def check():
 results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));pal={tuple(c) for c in results['palette']};merged={tuple(results['palette'][i]) for i in MERGE}
 for name in METHODS:
  folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'));grid=np.array(Image.open(folder/'sheet-grid.png'));strip=np.array(Image.open(folder/'sheet.png'))
  files=sorted((folder/'all-frames').glob('frame-*.png'));assert len(files)==results['frameCount']
  for i,p in enumerate(files):
   a=np.array(Image.open(p));b=np.array(Image.open(SOURCE/'all-frames'/p.name));assert a.shape==(192,192,4) and np.array_equal(a[:,:,3],b[:,:,3]);assert set(np.unique(a[:,:,3]))<={0,255}
   assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=(pal if name=='original' else merged)
   effects=np.any(np.all(b[:,:,:3,None].transpose(0,1,3,2)==np.array(results['palette'][32:])[None,None],axis=3),axis=2)&(b[:,:,3]>0)
   assert np.array_equal(a[effects],b[effects])
   if name=='original':assert np.array_equal(a,b)
  for j,i in enumerate(meta['sourceIndices']):
   a=np.array(Image.open(folder/f'frame-{j:02d}.png'));assert np.array_equal(a,np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png')))
   assert np.array_equal(a,grid[(j//6)*192:(j//6+1)*192,(j%6)*192:(j%6+1)*192]);assert np.array_equal(a,strip[:,j*192:(j+1)*192])
  for p in ['animation.png','animation.webp']:assert Image.open(folder/p).n_frames==len(meta['sourceIndices'])
  assert meta['colorProcessing']['mode']==name
  with zipfile.ZipFile(folder/'assets.zip') as z:
   assert z.testzip() is None
   for p in ['frames.json','color-settings.json','sheet-grid.png','animation.png','animation.gif']:
    assert z.read(p)==(folder/p).read_bytes()
   assert json.loads(z.read('color-settings.json'))['mode']==name
 for name,sig in results['sourceHashes'].items():assert hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==sig
 for url in re.findall(r'(?:src|href)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):
  if url!='pixel-color-lock.zip':assert (OUT/url).exists(),url
 save(OUT/'validation.json',dict(passed=True,fullFrames=results['frameCount']*3,selectedFrames=len(meta['sourceIndices'])*3,alphaExact=True,originalGeometryExact=True,sourceHashesPreserved=True,actualBrowserVerified=False))
 with zipfile.ZipFile(OUT/'pixel-color-lock.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and (p.suffix in ('.png','.webp','.gif','.json','.html') or p.name=='assets.zip'):z.write(p,p.relative_to(OUT))
 with zipfile.ZipFile(OUT/'pixel-color-lock.zip') as z:assert z.testzip() is None
 print('PASS geometry, palette, sheets, animations, source hashes, links, ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8')
 if len(sys.argv)>1 and sys.argv[1]=='check':check()
 elif len(sys.argv)>1 and sys.argv[1]=='build':build()
 else:process()
