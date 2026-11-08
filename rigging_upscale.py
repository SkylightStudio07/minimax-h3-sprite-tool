"""Export enlarged PSD and layer PNGs without changing the working revision."""
import io
import json
import shutil
import tempfile
import os
import zipfile
from pathlib import Path

from PIL import Image
import rigging_editor as editor
import rigging_super_resolution as super_resolution


def resize_layer(image, scale):
    # Pillow's RGBa mode resamples premultiplied alpha, avoiding dark fringes.
    return image.convert('RGBA').convert('RGBa').resize(
        (image.width * scale, image.height * scale), Image.Resampling.LANCZOS
    ).convert('RGBA')


def export_layers(folder: Path, scale: int, writer: Path, method: str = 'lanczos') -> bytes:
    super_resolution.validate_method(method)
    if type(scale) is not int or scale not in (2, 4):
        raise ValueError('확대 배율은 2배 또는 4배를 선택하세요.')
    manifest = editor.read_manifest(folder)
    width, height = manifest['canvas']['width'], manifest['canvas']['height']
    if width * height * scale * scale > 32_000_000:
        raise ValueError('확대 결과가 너무 큽니다. 더 낮은 배율을 선택하세요.')
    node = shutil.which('node')
    if not node:
        raise RuntimeError('PSD 생성에 필요한 Node.js를 찾을 수 없습니다.')
    with tempfile.TemporaryDirectory(prefix='rig-upscale-') as name:
        root = Path(name)
        records = dict(editor.layer_records(manifest))
        ai_files=[]
        with zipfile.ZipFile(folder / 'character-unity-parts.zip') as archive:
            editor._safe_extract(archive, root)
            for record in records.values():
                target = (root / record['file']).resolve()
                if not target.is_relative_to(root.resolve()):
                    raise ValueError('레이어 파일 경로를 확인하세요.')
                target.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(io.BytesIO(archive.read(record['file']))) as image:
                    enlarged = resize_layer(image, scale) if method=='lanczos' else image.convert('RGBA')
                enlarged.save(target)
                if method=='anime-ai':ai_files.append(target)
                for field in ('left', 'top', 'width', 'height'):
                    record[field] *= scale
        if ai_files:super_resolution.upscale_files(list(dict.fromkeys(ai_files)),scale)
        manifest['canvas']['width'] *= scale
        manifest['canvas']['height'] *= scale
        if manifest.get('rigEditor'):
            for bone in manifest['rigEditor']['bones']:
                for field in ('x', 'y', 'length'):
                    if field in bone:
                        bone[field] *= scale
        for clip in manifest.get('rigAnimations', {}).get('clips', []):
            for key in clip['keys']:
                for pose in key['pose'].values():
                    for field in ('dx', 'dy'):
                        if field in pose:
                            pose[field] *= scale
        manifest['unityPixelsPerUnit'] = float(manifest.get('unityPixelsPerUnit', 100)) * scale
        # Anchor coordinates use pixels; dimensionless ratios remain unchanged.
        coordinate_fields = {'x', 'y', 'cx', 'cy', 'x0', 'x1', 'y0', 'y1',
                             'icx', 'icy', 'closeY', 'neckTop', 'neckBottom', 'hairRootY'}
        def scale_anchors(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in coordinate_fields and type(child) in (int, float):
                        value[key] = child * scale
                    else:
                        scale_anchors(child)
        scale_anchors(manifest.get('anchors', {}))
        manifest['upscaleExport'] = {'scale': scale, 'method': 'alpha-safe-lanczos' if method=='lanczos' else 'realesrgan-anime6b-alpha-safe',
                                     'sourceRevision': manifest.get('editRevision', 0)}
        composite = Image.new('RGBA', (width * scale, height * scale))
        visibility = manifest.get('layerVisibility', {})
        for key in editor.effective_layer_order(manifest):
            record = records[key]
            if record.get('variantOf'):
                continue
            visible = (key.startswith('part:') or record.get('fade') == 'eyeOpen' or
                       record['id'] == 'eyebrow' or
                       record['id'] == ('mouth_open' if manifest.get('sourceMouthState') == 'slightly-open' else 'mouth_close'))
            if not visibility.get(key, visible):
                continue
            with Image.open(root / record['file']) as image:
                composite.alpha_composite(image.convert('RGBA'), (record['left'], record['top']))
        composite.save(root / 'composite.png')
        (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        editor._write_psd(root, manifest, composite, writer, node)
        unity_source = Path(__file__).parent / 'unity-package'
        if unity_source.is_dir():
            shutil.copytree(unity_source, root / 'Unity', dirs_exist_ok=True)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for item in root.rglob('*'):
                if item.is_file():
                    archive.write(item, item.relative_to(root).as_posix())
        return output.getvalue()


def apply_layers(folder: Path, scale: int, revision: int, writer: Path, unity_root: Path = None, method: str = 'lanczos') -> dict:
    """Commit an enlarged V1 package as a reversible working revision."""
    content = export_layers(folder, scale, writer, method)
    with tempfile.TemporaryDirectory(prefix='rig-upscale-apply-', dir=folder.parent) as name:
        root = Path(name)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            editor._safe_extract(archive, root)
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        manifest['editRevision'] = revision + 1
        (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        rebuilt = Path(name) / 'character-unity-parts.zip'
        # Avoid including the output ZIP in itself.
        with zipfile.ZipFile(rebuilt, 'w', zipfile.ZIP_DEFLATED) as archive:
            for item in root.rglob('*'):
                if item.is_file() and item != rebuilt:
                    archive.write(item, item.relative_to(root).as_posix())
        built = None
        if unity_root is not None:
            import rigging_v2
            pose = None
            existing = folder / rigging_v2.V2_FILENAME
            if existing.is_file():
                with zipfile.ZipFile(existing) as archive:
                    old_rig = json.loads(archive.read('rig-v2.json'))
                if old_rig.get('poseSource') == 'user-points':
                    bones = {bone['name']: bone for bone in old_rig['bones']}
                    pose = {key: {'x': bones[key]['x'] * scale, 'y': bones[key]['y'] * scale}
                            for key in rigging_v2.POSE_KEYS}
            built = rigging_v2.build_package(root, unity_root, revision + 1, pose=pose)
        backup = folder / 'revisions' / f'{revision:04d}'
        backup.mkdir(parents=True, exist_ok=True)
        for filename in editor.VERSION_FILES:
            if not (backup / filename).exists():
                shutil.copy2(folder / filename, backup / filename)
        staged = {}
        filenames = list(editor.VERSION_FILES)
        if built:
            filenames.append(rigging_v2.V2_FILENAME)
            if (folder / rigging_v2.V2_FILENAME).exists():
                shutil.copy2(folder / rigging_v2.V2_FILENAME, backup / rigging_v2.V2_FILENAME)
        try:
            for filename in filenames:
                source = rebuilt if filename == 'character-unity-parts.zip' else root / filename
                staged[filename] = folder / ('.upscale-' + filename)
                shutil.copy2(source, staged[filename])
            for filename in filenames:
                os.replace(staged[filename], folder / filename)
        except Exception:
            for filename in filenames:
                if (backup / filename).exists():
                    shutil.copy2(backup / filename, folder / filename)
                else:
                    (folder / filename).unlink(missing_ok=True)
            raise
        finally:
            for target in staged.values():
                target.unlink(missing_ok=True)
    return {'revision': revision + 1, 'manifest': manifest, 'bones': built['bones'] if built else None}
