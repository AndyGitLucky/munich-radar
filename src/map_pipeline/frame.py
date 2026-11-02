"""Versioned Imagegen cloud artwork and deterministic masks outside Munich."""
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .core import digest, identity, load, now, safe_id, save


def folder_for(workspace, version):
    return workspace.path('frames/' + safe_id(version))


def import_frame(workspace, version, source, references=None, variants=None, prompts=None):
    folder = folder_for(workspace, version)
    if (folder / 'request.json').exists():
        raise ValueError('Frame already imported; use a new version')
    prompt = folder / 'prompt.md'
    if not prompt.is_file():
        raise ValueError('Save the exact Imagegen prompt as frames/VERSION/prompt.md first')
    source = Path(source).resolve()
    with Image.open(source) as image:
        if image.format != 'PNG' or min(image.size) < 512:
            raise ValueError('Expected native Imagegen PNG, at least 512 pixels per edge')
        if image.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise ValueError('Cloud texture must be opaque')
        size = list(image.size)
    raw = folder / 'raw.png'
    if raw.resolve() != source:
        shutil.copyfile(source, raw)
    references = references or ['baseline/images/r04c03.png']
    variants = variants or []
    prompts = prompts or []
    textures = [(raw.relative_to(workspace.root).as_posix(), digest(raw))]
    for path in variants:
        with Image.open(workspace.path(path)) as image:
            if image.size != tuple(size) or image.convert('RGBA').getchannel('A').getextrema() != (255,255):
                raise ValueError('Cloud variants must have matching native size and be opaque')
        textures.append((path, digest(workspace.path(path))))
    recipe = {'texture': 'raw.png', 'nativeSize': size, 'overlap': 192,
              'maskBlur': 64, 'maskClear': 105, 'maskOpaque': 24,
              'seed': 73109, 'textures': [{'path': p, 'sha256': h} for p,h in textures],
              'note': 'Native cloud pixels with seeded, staggered feathered placements; no source scaling, mirroring or recoloring.'}
    save(folder / 'recipe.json', recipe)
    request = {'version': version, 'status': 'awaiting visual review',
               'promptSha256': digest(prompt), 'imageSha256': digest(raw),
               'recipeSha256': digest(folder / 'recipe.json'),
               'references': [{'path': ref, 'sha256': digest(workspace.path(ref))} for ref in references],
               'additionalPrompts': [{'path': ref, 'sha256': digest(workspace.path(ref))} for ref in prompts],
               'generatedSource': str(source), 'imported': now(), 'nativeSize': size}
    save(folder / 'request.json', request)
    return selected_frame(workspace, version)


def selected_frame(workspace, version):
    folder = folder_for(workspace, version)
    request = load(folder / 'request.json')
    return {'version': version, 'path': (folder / 'raw.png').relative_to(workspace.root).as_posix(),
            'sha256': request['imageSha256'], 'recipeSha256': request['recipeSha256']}


def check_frame(workspace, item, require_review=False):
    folder = folder_for(workspace, item['version'])
    request = load(folder / 'request.json')
    for name, key in [('prompt.md', 'promptSha256'), ('raw.png', 'imageSha256'), ('recipe.json', 'recipeSha256')]:
        if digest(folder / name) != request[key]:
            raise ValueError('Cloud frame provenance changed: ' + name)
    if item != selected_frame(workspace, item['version']):
        raise ValueError('Cloud frame selection changed')
    recipe = load(folder / 'recipe.json')
    for ref in request['references'] + request.get('additionalPrompts', []) + recipe.get('textures', []):
        if digest(workspace.path(ref['path'])) != ref['sha256']:
            raise ValueError('Cloud frame reference changed')
    if require_review:
        review = request.get('review', {})
        if review.get('decision') != 'accept' or review.get('identity') != identity(item):
            raise ValueError('Visual review required: cloud frame')
    return recipe


def review_frame(workspace, version, decision, note):
    item = selected_frame(workspace, version)
    check_frame(workspace, item)
    if decision not in ('accept', 'reject') or not note.strip():
        raise ValueError('Record a visual decision and observations')
    if decision == 'reject' and workspace.state().get('frame') == item:
        raise ValueError('Roll back the active frame before rejecting it')
    folder = folder_for(workspace, version)
    request = load(folder / 'request.json')
    request['review'] = {'decision': decision, 'note': note, 'identity': identity(item), 'at': now()}
    request['status'] = 'visually ' + ('accepted' if decision == 'accept' else 'rejected')
    save(folder / 'request.json', request)
    return request['review']


def city_mask(plan):
    mask = Image.new('L', tuple(plan['imageSize']), 0)
    draw = ImageDraw.Draw(mask)
    west, _, _, north = plan['bounds']
    for ring in plan['cityOutline']:
        draw.polygon([((x-west)*plan['scale'], (north-y)*plan['scale']) for x, y in ring], fill=255)
    return mask


def make_mask(workspace, item, output):
    recipe = check_frame(workspace, item)
    plan = workspace.plan()
    city = city_mask(plan)
    # A soft allowance follows the geographic boundary. Exact city pixels and
    # every protected landmark stay clear, including small disconnected areas.
    blurred = city.filter(ImageFilter.GaussianBlur(recipe['maskBlur']))
    table = [round(255 * max(0, min(1, (recipe['maskClear'] - v) /
               (recipe['maskClear'] - recipe['maskOpaque'])))) for v in range(256)]
    mask = blurred.point(table)
    mask.paste(0, mask=city)
    draw = ImageDraw.Draw(mask)
    for landmark in plan['landmarks']:
        a, b, c, d = landmark['protectedRect']
        draw.rectangle((int(a)-8, int(b)-8, int(c)+8, int(d)+8), fill=0)
    mask.save(output)
    Image.merge('LA', (Image.new('L', mask.size, 255), mask)).save(output.with_name('cloud-alpha.png'))
    return recipe


def verify_frame(folder, plan):
    ground = Image.open(folder / 'ground.png').convert('RGBA')
    master = Image.open(folder / 'master.png').convert('RGBA')
    city = city_mask(plan)
    mask = Image.open(folder / 'cloud-mask.png')
    covered = 0
    for y in range(0, master.height, 128):
        box = (0, y, master.width, min(master.height, y+128))
        before = np.asarray(ground.crop(box))
        after = np.asarray(master.crop(box))
        protected = np.asarray(city.crop(box)) > 0
        if np.any(before[protected] != after[protected]):
            raise ValueError('Cloud frame changed city pixels')
        if np.any(after[:, :, 3] != 255):
            raise ValueError('Cloud frame left transparent pixels in rectangle')
        alpha = np.asarray(mask.crop(box))
        if np.any(alpha[protected]):
            raise ValueError('Cloud mask overlaps Munich')
        covered += int(np.count_nonzero(alpha))
    return {'rectangularOpaque': True, 'cityMaxChannelDifference': 0,
            'maskedOutsidePixels': covered, 'groundSha256': digest(folder / 'ground.png'),
            'maskSha256': digest(folder / 'cloud-mask.png')}
