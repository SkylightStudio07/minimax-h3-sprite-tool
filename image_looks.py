"""Versioned visual presets; generation keeps the user's editable numeric settings."""
import json
from pathlib import Path

CATALOG=Path(__file__).resolve().parent/'web/assets/image-looks.json'


def catalog():
    return json.loads(CATALOG.read_text(encoding='utf-8'))


def apply(result, look_id):
    if look_id in (None,''):return
    if not isinstance(look_id,str):raise ValueError('그림체 프리셋을 확인하세요.')
    data=catalog()
    look=next((x for x in data['looks'] if x['id']==look_id),None)
    if look is None or look['model']!=result['model']:
        raise ValueError('현재 모델에 맞는 그림체 프리셋을 다시 적용하세요.')
    result.update(lookId=look_id,lookName=look['name'],lookVersion=data['version'],lookPrompt=look['prompt'],lookNegativePrompt=look['negative'])
    if look['model']=='soya-anima-flanime':
        result['workflowBasePrompt']=result['resolvedPrompt']
        result['workflowBaseNegativePrompt']=result['resolvedNegativePrompt']
        if look.get('basePrompt'):
            result['workflowBasePrompt']+=', '+look['basePrompt']
        if look.get('baseNegative'):
            result['workflowBaseNegativePrompt']+=', '+look['baseNegative']
        if look.get('finalTone'):
            if look['finalTone'] not in ('grayscale','blue','sepia'):raise ValueError('그림체 마감 설정을 확인하세요.')
            result['lookFinalTone']=look['finalTone']
        config=look.get('workflow',{})
        bounds={'kieedStrength':(0,1.2),'detailStrength':(0,1.2),'refineDenoise':(.05,.6),'vibrance':(-100,100),'saturation':(-100,100)}
        clean={}
        for key,value in config.items():
            if key not in bounds or type(value) not in (int,float) or not bounds[key][0]<=value<=bounds[key][1]:
                raise ValueError('그림체 워크플로 설정을 확인하세요.')
            clean[key]=value
        result['lookWorkflow']=clean
    result['resolvedPrompt']+=', '+look['prompt']
    if look['negative']:result['resolvedNegativePrompt']+=', '+look['negative']
    return look
