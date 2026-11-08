"""Register reviewed Civitai snapshots; never enable weights before generation tests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    models = []
    catalog_path = ROOT / 'web/assets/image-styles.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    snapshots = {mid: json.loads((ROOT / f'data/research/civitai-{mid}.json').read_text(encoding='utf-8'))
                 for mid in (2061456, 2639339)}

    def entry(mid, vid, fid, relative_path, identity):
        info = snapshots[mid]
        version = next(v for v in info['modelVersions'] if v['id'] == vid)
        file = next(f for f in version['files'] if f['id'] == fid)
        permissions = {k: info.get(k) for k in ('allowNoCredit', 'allowCommercialUse', 'allowDerivatives', 'allowDifferentLicense')}
        item = dict(id=identity, url=f'https://civitai.com/api/download/models/{vid}?fileId={fid}',
                    relative_path=relative_path, size=round(file['sizeKB'] * 1024),
                    sha256=file['hashes']['SHA256'].lower(), metadata=dict(
                        modelId=mid, versionId=vid, fileId=fid, name=info['name'], version=version['name'],
                        creator=info.get('creator', {}).get('username', ''), permissions=permissions,
                        source=f'https://civitai.com/models/{mid}?modelVersionId={vid}',
                        descriptionSnapshot=f'data/research/civitai-{mid}.json'))
        models.append(item)
        return item

    variants = [
        ('fsthicc-anima', 'FSThicc · 굵은 선 / Anima', 'anima', 3135585, 3016316, 'fsthicc-anima-v1.safetensors'),
        ('fsthicc-anima-b', 'FSThicc · B-side / Anima', 'anima', 3135604, 3016333, 'fsthicc-anima-v1-b-side.safetensors'),
        ('fsthicc-illustrious', 'FSThicc · 굵은 선 / Illustrious', 'illustrious', 3059910, 2938521, 'fsthicc-illustrious-v4.safetensors'),
    ]
    for identity, name, family, vid, fid, filename in variants:
        item = entry(2061456, vid, fid, 'models/loras/requested/' + filename, identity)
        style = dict(id=identity, name=name, family=family, enabled=False, experimental=True,
                     verification='다운로드·실생성 검증 대기',
                     description='굵은 검은 윤곽선과 곡선 체형을 함께 강조합니다. 가슴 등 신체 비율이 과장될 수 있어 낮은 강도부터 비교하세요.' +
                                 (' Illustrious 전용으로 현재 Anima/Soya와 호환되지 않습니다.' if family == 'illustrious' else ' 2.9B에서는 LoRA 블록 재매핑 검증이 필요합니다.'),
                     filename='requested/' + filename, versionId=vid, modelId=2061456,
                     creator=item['metadata']['creator'], source=item['metadata']['source'],
                     triggers=['thick black outline'], strength=0.3, previews=[],
                     license='제작자 크레딧 요구. 표시된 상업 허용은 RentCivit만이며 게임 이용 허용을 확인한 상태가 아닙니다. 원문 및 기반 모델 조건 확인 필요.',
                     permissions=item['metadata']['permissions'], downloadUrl=item['url'],
                     sha256=item['sha256'], bytes=item['size'],
                     authorRecommendedSettings=dict(cfg=[5, 7], steps=25, samplers=['Euler A', 'DPM++ 2M Karras'],
                         triggerRequired=False, note='페이지 공통 권장값. Anima Turbo 및 Soya에 그대로 적용하지 말 것. 강도 0.3은 로컬 시험 시작값이며 제작자 권장값 아님.'))
        old = next((s for s in catalog['styles'] if s['id'] == identity), None)
        if old and old.get('sha256') == style['sha256']:
            for key in ('enabled', 'verification', 'previews'):
                style[key] = old.get(key, style[key])
        catalog['styles'] = [s for s in catalog['styles'] if s['id'] != identity] + [style]

    candidates = []
    for identity, vid, fid, filename, params in [
        ('silvermoon-anima-v23', 3217855, 3099649, 'silvermoonmixAnimaEvolved_v23.safetensors',
         dict(sampler='euler_ancestral', steps=24, stepRange=[20, 28], cfg=4)),
        ('silvermoon-anima-v23-29b-turbo', 3335132, 3221561, 'silvermoonmixAnimaEvolved_v2329BTurbo.safetensors',
         dict(sampler='er_sde', steps=10, stepRange=[8, 12], cfg=1)),
    ]:
        item = entry(2639339, vid, fid, 'models/diffusion_models/' + filename, identity)
        candidates.append(dict(id=identity, enabled=False, experimental=True, verification='다운로드 후 별도 그래프 실생성 검증 필요',
            **item['metadata'], diffusionModel=filename,
            textEncoder='qwen_3_06b_base.safetensors', vae='qwen_image_vae.safetensors',
            recommendedSettings=dict(**params, negativePrompt='', artistPrefix='@'),
            compatibilityNotes='2.9B는 최신 ComfyUI 및 기존 2B LoRA 블록 재매핑 검증 필요. 기존 Soya 그래프에 자동 대체 금지.',
            license='Civitai 표시상 Image 포함 상업 이용 허용. 기반 Anima 조건 별도 확인.',
            sha256=item['sha256'], bytes=item['size']))
    # Both versions publish identical encoder/VAE hashes; reuse the installed files
    # after downloader verification instead of storing misleading duplicate names.
    entry(2639339, 3217855, 3099644, 'models/text_encoders/qwen_3_06b_base.safetensors', 'silvermoon-shared-text-encoder')
    entry(2639339, 3217855, 3099640, 'models/vae/qwen_image_vae.safetensors', 'silvermoon-shared-vae')
    save(catalog_path, catalog)
    save(ROOT / 'data/fsthicc-silvermoon-import.json', dict(models=models))
    save(ROOT / 'data/silvermoon-model-candidates.json', dict(
        note='준비용 후보 목록이며 image_engine.MODELS에 자동 등록하지 않음. 기본값은 Soya 유지.', models=candidates))
    print(json.dumps(dict(loraCards=len(variants), modelCandidates=len(candidates),
                         newDownloadBytes=sum(m['size'] for m in models[:5])), ensure_ascii=False))


if __name__ == '__main__':
    main()
