"""Replay both approved native clips through the production runner. Never submits a GPU job."""
import base64,hashlib,io,json,sys
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
import idle_tool as engine,sprite_gif
OUT=ROOT/'outputs/site-subtle-vfx-20261020'
SOURCE=ROOT/'outputs/normal-sword-vfx-subtle-20261020'

def main():
 catalog=json.loads((ROOT/'web/assets/sprite-examples/catalog.json').read_text(encoding='utf-8'));reports={}
 for name in ('slash','spin'):
  recipe=next(x['recipe'] for x in catalog['examples'] if x['id']=='normal-subtle-'+name)
  p=dict(recipe,imageData=base64.b64encode((SOURCE/name/'reference.png').read_bytes()).decode(),
   assetSpec=dict(type='side',facing='right',directionCount=1))
  result={};response=Mock(ok=True);response.json.return_value={'prompt_id':'replay-'+name}
  history=Mock();history.json.return_value={'replay-'+name:{'status':{'completed':True,'status_str':'success'}}}
  with patch.object(engine,'RESULT_ROOT',OUT),patch.object(engine,'upload_image',return_value='reference.png'),\
   patch.object(engine,'update_job',side_effect=lambda jid,**kw:result.update(kw)),\
   patch.object(engine.requests,'post',return_value=response) as post,patch.object(engine.requests,'get',return_value=history),\
   patch.object(engine,'find_saved_video',return_value=SOURCE/name/'raw.mp4'):
   engine.run_job(name,p)
  assert result['state']=='complete',result
  assert result['transparentSheet'] and result['frameCount']==24
  assert result['backgroundRemoval']=='flat'
  folder=OUT/name;action=p['animationType'];raw=folder/f'{action}_raw.mp4'
  assert hashlib.sha256(raw.read_bytes()).digest()==hashlib.sha256((SOURCE/name/'raw.mp4').read_bytes()).digest()
  with Image.open(folder/'reference_prepared.png') as actual,Image.open(SOURCE/name/'reference-prepared.png') as expected:
   np.testing.assert_array_equal(np.asarray(actual.convert('RGB')),np.asarray(expected.convert('RGB')))
  graph=post.call_args.kwargs['json']['prompt'];text=graph['6']['inputs']['prompt']
  assert graph['10']['inputs']['steps']==20 and 'last_frame' not in graph['6']['inputs']
  assert p['prompt'] in text and 'forearm-length' in text
  for term in ('starburst','energy crescent','No complete turn','auburn','cream jacket'):assert term not in text
  with Image.open(folder/f'{action}_transparent.png') as sheet:
   assert sheet.size==(768*8,768*3)
   images=sprite_gif.split_sheet(sheet,8,3,24)
  assert sum(result['sheetTimingMs'])==result['motionTiming']['totalMs']
  data,gif=sprite_gif.encode(images,result['sheetTimingMs']);(folder/'animation.gif').write_bytes(data)
  assert abs(gif['totalMs']-result['motionTiming']['totalMs'])<=10
  (folder/'submitted-workflow.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
  reports[name]=dict(passed=True,actualGpuSubmission=False,referencePixelsMatch=True,rawVideoPreserved=True,
   result=result,gif=gif)
  print('PASS production small-trail pipeline:',name,flush=True)
 (OUT/'validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
