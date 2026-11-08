"""Fresh source-video matte with protected interiors and coherent ink boundary."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import gc,json,shutil,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av,cv2,numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import refine_variations_edges_20261102 as previews

OUT=ROOT/'outputs/blonde-from-raw-20261102'
SOURCE=ROOT/'outputs/blonde-grip-retry-20261101'
MOTIONS={'idle':'01-blonde-idle-grip','attack':'02-blonde-fire-v2'}

def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def matte(raw,action):
    rgb=np.array(raw.convert('RGB'),dtype=float)
    bg=np.median(np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1])),axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2)
    sem=np.array(image_background.remove(raw))[:,:,3]
    protected=ndimage.distance_transform_edt(sem>230)>3
    alpha=np.clip((delta-6)/22,0,1);alpha[protected]=1
    opaque=alpha>.98
    distance,indices=ndimage.distance_transform_edt(~opaque,return_indices=True)
    prior=rgb[indices[0],indices[1]];axis=prior-bg;norm=(axis*axis).sum(2)
    fit=np.clip(((rgb-bg)*axis).sum(2)/np.maximum(norm,1),0,1)
    residual=np.linalg.norm(rgb-bg-fit[:,:,None]*axis,axis=2)
    band=(alpha<1)&(alpha>0)&(distance<3)&(residual<12)&(norm>40**2)
    alpha[band]=fit[band];alpha[alpha<.03]=0
    fg=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.03),0,255)
    fg[alpha>.98]=rgb[alpha>.98]
    original=np.rint(np.dstack((fg,alpha*255))).astype('uint8')
    original[original[:,:,3]==0]=0
    yy,xx=np.indices(delta.shape)
    effect_roi=(xx<240)&(yy<500)
    warm=effect_roi&(rgb[:,:,0]>210)&(rgb[:,:,1]>145)&(rgb[:,:,0]-rgb[:,:,2]>55)
    is_flash=action=='attack' and warm.sum()>=3
    candidate=original[:,:,3]>180
    if is_flash:
        candidate &= (sem>160)|(delta>55)
        candidate &= (xx>240)|(rgb.mean(2)<bg.mean()-25)
    labels,n=ndimage.label(candidate)
    sizes=np.bincount(labels.ravel());sizes[0]=0
    main=labels==np.argmax(sizes)
    depth=ndimage.distance_transform_edt(main);dist=ndimage.distance_transform_edt(~main)
    labels_gc=np.full(main.shape,cv2.GC_BGD,dtype='uint8')
    labels_gc[dist<2]=cv2.GC_PR_BGD
    labels_gc[main]=cv2.GC_PR_FGD
    labels_gc[depth>4]=cv2.GC_FGD
    white=(rgb.min(2)>165)&(np.ptp(rgb,axis=2)<30)
    labels_gc[main&(depth<4)&white]=cv2.GC_PR_BGD
    labels_gc[main&(depth<1.5)&white]=cv2.GC_BGD
    cv2.setRNGSeed(0)
    cv2.grabCut(rgb.astype('uint8'),labels_gc,None,np.zeros((1,65)),np.zeros((1,65)),5,cv2.GC_INIT_WITH_MASK)
    keep=(labels_gc==cv2.GC_FGD)|(labels_gc==cv2.GC_PR_FGD)
    smooth=ndimage.gaussian_filter(keep.astype(float),.65)
    final_alpha=np.clip((smooth-.1)/.8,0,1)
    a=original.copy();a[:,:,3]=np.rint(final_alpha*255).astype('uint8')
    if is_flash:a[dist>3]=0
    else:a[dist>3]=original[dist>3]
    # Eye wisps and flash/smoke use their fresh source matte, never body-edge cuts.
    red=(rgb[:,:,0]-rgb[:,:,1]>25)&(rgb[:,:,0]-rgb[:,:,2]>20)&(yy<340)&(xx>340)
    flash=effect_roi&(dist>2)&is_flash
    a[red|flash]=original[red|flash]
    if is_flash:
        physical_alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
        physical_alpha[physical_alpha<.035]=0
        unmix=np.clip((rgb-bg*(1-physical_alpha[:,:,None]))/np.maximum(physical_alpha[:,:,None],.02),0,255)
        a[flash,:3]=np.rint(unmix[flash]).astype('uint8')
        a[flash,3]=np.rint(physical_alpha[flash]*255).astype('uint8')
    core=depth>4
    a[core,3]=255
    a[core,:3]=rgb.astype('uint8')[core]
    a[a[:,:,3]==0]=0
    assert np.all(a[:,:,3][core]==255)
    assert np.array_equal(a[:,:,:3][core],rgb.astype('uint8')[core])
    return Image.fromarray(a),dict(interiorRGBUnchanged=True,interiorOpaque=True,corePixels=int(core.sum()),boundaryMethod='graphcut with protected core and subpixel alpha',redEffectPreserved=True)

def build():
    cards=[]
    for action in MOTIONS:
        if not (OUT/action/'game-animation.webp').exists():continue
        cards.append(f'<article><h2>{action}</h2><img class="cut" src="{action}/game-animation.webp?v=raw1"><p><a href="{action}/game-animation.gif">GIF</a> · <a href="{action}/native-sheet.png">PNG 시트</a> · <a href="{action}/raw.mp4">생성 원본</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>금발 · 원본 영상부터 다시 누끼</title><style>:root{--bg:#142436}body{background:#202632;color:#eee;font:16px/1.6 system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}article{width:768px;max-width:100%}.cut{width:100%;background:var(--bg)}a{color:#cec3ff}button{padding:10px;margin:4px}</style><h1>금발 · 원본 영상부터 다시 누끼</h1><p>기존 보정을 누적하지 않고 원본 MP4부터 처리. 셔츠·피부·몸 안쪽 색과 불투명도를 보존하고, 바깥 경계를 연속된 선으로 정리했습니다. 768px 원본 해상도입니다.</p><button onclick="document.documentElement.style.setProperty('--bg','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--bg','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--bg','#226b54')">초록</button><p><a href="blonde-from-raw-handoff.zip">전체 ZIP</a> · <a href="comparison.jpg">이전 결과와 비교</a></p><main>'''+''.join(cards)+'</main></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True)
    for name in ('source-original.png','reference.png','source.json'):
        shutil.copy2(SOURCE/MOTIONS['idle']/name,OUT/name)
    base.OUT=OUT;base.SOURCE=OUT/'source-original.png'
    base.ACTIONS={a:dict(title=a,loop=a=='idle',padding=30,frames=24) for a in MOTIONS}
    base.build=build;base.configure()
    for action,mid in MOTIONS.items():
        folder=OUT/action;folder.mkdir(exist_ok=True)
        for name in ('settings.json','reference-prepared.png','native-v1-workflow.json'):
            shutil.copy2(SOURCE/mid/name,folder/name)
        raw=ROOT/'outputs/comfy/blonde_grip_retry_20261101'/(mid+'_00001_.mp4')
        shutil.copy2(raw,folder/'raw.mp4')
        dest=folder/'all-frames';dest.mkdir(exist_ok=True)
        records=[]
        with av.open(str(raw)) as video:
            for i,frame in enumerate(video.decode(video=0)):
                cut,info=matte(frame.to_image(),action);cut.save(dest/f'frame-{i:03d}.png')
                records.append(dict(frame=i,**info))
                if i%12==0:
                    print('FRESH_MATTE',action,i,flush=True)
                    save(OUT/'progress.json',dict(phase='matting',action=action,frame=i,totalFrames=73))
        save(folder/'matte-process.json',dict(fromRawVideo=True,previousMattesUsed=False,frames=records))
        save(folder/'review.json',dict(reviewed=False,note='원본 영상에서 새로 추출. 셔츠·피부 내부 RGB와 불투명도 보존.'))
    finish()

def finish():
    base.OUT=OUT;base.SOURCE=OUT/'source-original.png'
    base.ACTIONS={a:dict(title=a,loop=a=='idle',padding=30,frames=24) for a in MOTIONS}
    base.build=build;base.configure()
    save(OUT/'idle/selection.json',dict(start=0,end=71))
    base.export()
    for action in MOTIONS:previews.native_previews(OUT,action)
    # Paired native-size contact comparison with the rejected v2.
    compare=Image.new('RGB',(1536,1536));draw=ImageDraw.Draw(compare)
    for row,(action,i) in enumerate([('idle',0),('attack',17),('attack',31)]):
        for col,(path,color) in enumerate([(ROOT/'outputs/character-variations-cutout-v2-20261102'/ 'blonde'/action/'all-frames'/f'frame-{i:03d}.png','#142436'),(OUT/action/'all-frames'/f'frame-{i:03d}.png','#142436'),(OUT/action/'all-frames'/f'frame-{i:03d}.png','#fff4dc')]):
            with Image.open(path) as im:
                bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im.convert('RGBA'));compare.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512))
            draw.text((col*512+8,row*512+8),'OLD V2' if col==0 else 'FRESH RAW',fill='red')
    compare.save(OUT/'comparison.jpg',quality=97)
    build()
    with zipfile.ZipFile(OUT/'blonde-from-raw-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('preview.html','comparison.jpg','source-original.png','source.json','reference.png','game-registration.json'):z.write(OUT/name,name)
        for action in MOTIONS:
            folder=OUT/action
            for name in ('game-animation.webp','game-animation.gif','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','raw.mp4','settings.json','matte-process.json','matte-review.jpg'):z.write(folder/name,action+'/'+name)
            meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for i in meta['sourceIndices']:z.write(folder/'all-frames'/f'frame-{i:03d}.png',action+f'/frames/frame-{i:03d}.png')
    with zipfile.ZipFile(OUT/'blonde-from-raw-handoff.zip') as z:assert z.testzip() is None
    save(OUT/'progress.json',dict(phase='complete',actions=2,fromRawVideo=True,previousMattesUsed=False))
    print('FRESH_BLONDE_PACKAGED',flush=True)

if __name__=='__main__':main()
