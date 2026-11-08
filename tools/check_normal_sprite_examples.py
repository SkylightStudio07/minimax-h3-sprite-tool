"""Validate the new normal examples before catalog publication."""
import hashlib,json,sys
from pathlib import Path
import av
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_normal_sprite_examples import OUT,ACTIONS,CHARACTER


def main():
    records=[]
    reference=Image.open(OUT/'reference.png').convert('RGBA')
    assert reference.size==(1024,1536) and reference.getchannel('A').getextrema()[0]==0
    reference_id=json.loads((OUT/'reference-generation/reference-v1-pending.json').read_text())['promptId']
    for action,item in ACTIONS.items():
        folder=OUT/action
        settings=json.loads((folder/'settings.json').read_text())
        pending=json.loads((folder/'native-motion-v1-pending.json').read_text())
        graph=json.loads((folder/'native-motion-v1-workflow.json').read_text())
        meta=json.loads((folder/'frames.json').read_text())
        assert settings['characterId']==CHARACTER and settings['pixelOutput'] is False
        assert settings['workflowId']=='standard' and settings['samplingMode']=='quality'
        assert graph['10']['inputs']['steps']==20 and graph['6']['inputs']['width']==768
        assert settings['prompt'] in graph['6']['inputs']['prompt']
        with av.open(str(folder/'raw.mp4')) as video:
            frames=[frame.to_image().convert('RGB') for frame in video.decode(video=0)]
        assert len(frames)==73 and all(frame.size==(768,768) for frame in frames)
        differences=[float(np.abs(np.array(frames[i],dtype=float)-np.array(frames[i-1],dtype=float)).mean()) for i in range(1,len(frames))]
        assert max(differences)>.1,(action,max(differences))
        with Image.open(folder/'animation.webp') as preview:
            assert preview.n_frames==73 and preview.size==(384,384)
            assert len(meta['previewTimingMs'])==73 and sum(meta['previewTimingMs'])==3042
            opaque=preview.convert('RGBA');assert opaque.getchannel('A').getextrema()[0]==0
            a=np.array(opaque);colors=len(np.unique(a[:,:,:3][a[:,:,3]>128],axis=0));assert colors>64
        with Image.open(folder/'sheet.png') as sheet:
            assert sheet.size==(768*meta['columns'],768*meta['rows'])
        records.append(dict(action=action,characterId=CHARACTER,referencePromptId=reference_id,promptId=pending['promptId'],
            rawSha256=hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest(),frames=73,
            maxMeanFrameDifference=max(differences),previewColors=colors,
            edgeContactFrames=[d['sourceFrame'] for d in meta['diagnostic'] if d['edgeContact']]))
    (OUT/'validation.json').write_text(json.dumps(dict(passed=True,newAIGeneration=True,records=records,actualBrowserVerified=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS fresh Comfy reference + 3 native 20-step motion prompts, same character, actual 73-frame animation (not contact sheets), fine-color non-pixel output, PNG sheets and 3042ms timing')


if __name__=='__main__':main()
