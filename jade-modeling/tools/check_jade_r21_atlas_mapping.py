"""Read-only cross-check of serialized r21 source and atlas texture mappings.

This checks the stored data, not Cubism's native renderer or its exporter.
"""
import argparse
import copy
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from cmo3_inventory import CaffArchive

if not __debug__:
    raise RuntimeError('Validation requires assertions: run Python without -O or PYTHONOPTIMIZE.')

KEYS = ('m00', 'm01', 'm02', 'm10', 'm11', 'm12')


def named(node, tag, name):
    found = [n for n in node.iter(tag) if n.get('xs.n') == name]
    assert len(found) == 1, (tag, name, len(found))
    return found[0]


def matrix(node):
    return np.vstack((np.array([float(node.get(k)) for k in KEYS]).reshape(2, 3), [0, 0, 1]))


def transform(points, affine):
    return (np.column_stack((points, np.ones(len(points)))) @ affine.T)[:, :2]


def load(path):
    data = path.read_bytes()
    archive = CaffArchive.parse(data)
    root = ET.fromstring(archive.read_unique_path('main.xml', 256*1024*1024))
    items = [n for n in root.iter() if n.get('xs.id')]
    ids = {n.get('xs.id'): n for n in items}
    assert len(ids) == len(items), 'Duplicate object IDs'
    assert not [n.get('xs.ref') for n in root.iter() if n.get('xs.ref') and n.get('xs.ref') not in ids], 'Unresolved object references'
    return data, archive, root, ids


def raster(archive, resource):
    with Image.open(io.BytesIO(archive.read_unique_path(named(resource, 'file', 'imageFileBuf').get('path'), 256*1024*1024))) as image:
        return np.asarray(image.convert('RGBA')).copy()


def source_points(mesh, ids):
    texture = ids[named(mesh, 'GTexture2D', 'texture').get('xs.ref')]
    resource = ids[named(texture, 'CImageResource', 'srcImageResource').get('xs.ref')]
    uv = np.array([float(v) for v in named(mesh, 'float-array', 'uvs').text.split()]).reshape(-1, 2)
    triangles = np.array([int(v) for v in named(mesh, 'int-array', 'indices').text.split()]).reshape(-1, 3)
    uv = np.concatenate((uv, uv[triangles].mean(axis=1)))
    logical = matrix(named(texture, 'CAffine', 'transformImageResource01toLogical01'))
    pixels = transform(uv, np.linalg.inv(logical)) * [int(resource.get('width')), int(resource.get('height'))]
    return resource, pixels


def sample(image, points):
    # Pixel centers live at x+.5/y+.5. Outside the resource is transparent.
    points = points - .5
    low = np.floor(points).astype(int)
    f = points - low
    out = np.zeros((len(points), 4))
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        xy = low + [dx, dy]
        valid = (xy[:, 0] >= 0) & (xy[:, 0] < image.shape[1]) & (xy[:, 1] >= 0) & (xy[:, 1] < image.shape[0])
        weight = (f[:, 0] if dx else 1-f[:, 0]) * (f[:, 1] if dy else 1-f[:, 1])
        out[valid] += image[xy[valid, 1], xy[valid, 0]] * weight[valid, None]
    return out


def canonical(node, ignore_sampling=False):
    node = copy.deepcopy(node)
    if ignore_sampling:
        named(node, 'GTexture2D', 'texture').set('xs.ref', '#ignored')
        named(node, 'float-array', 'uvs').text = 'ignored'
    for item in node.iter():
        item.tail = None
        if item.text and not item.text.strip():
            item.text = None
    return ET.tostring(node)


def check(source, candidate):
    old_data, old_archive, old_root, old_ids = load(source)
    data, archive, root, ids = load(candidate)
    images = {named(n, 'CModelImageGuid', 'guid').get('xs.ref'): n for n in root.iter('CModelImage') if named(n, 'CModelImageGuid', 'guid').get('xs.ref')}
    pages, placements = {}, {}
    for atlas in root.iter('CTextureAtlas'):
        if not atlas.get('xs.id'):
            continue
        guid = named(atlas, 'CTextureAtlasGuid', 'guid').get('xs.ref')
        pages[guid] = raster(archive, ids[named(atlas, 'CImageResource', 'cachedAtlasImage').get('xs.ref')])
        for entry in atlas.iter('ModelImageEntry'):
            key = named(entry, 'CModelImageGuid', 'modelImageGuid').get('xs.ref')
            assert key not in placements, 'Duplicate placement'
            p = named(entry, 'GTransform2', 'materialLocalToAtlasTransform')
            position = named(p, 'GVector2', 'position')
            offset = np.array([float(named(position, 'f', k).text) for k in ('x', 'y')])
            scale = named(p, 'GVector2', 'scale')
            assert [float(named(scale, 'f', k).text) for k in ('x', 'y')] == [1., 1.]
            assert float(named(p, 'f', 'eulerAngle').text) == 0
            affine = matrix(named(entry, 'CAffine', 'atlasLocalToCanvasTransform'))
            placements[key] = (guid, offset, affine)
    rows, cached = [], {}
    mesh_ids = [n.get('xs.id') for n in root.iter('CArtMeshSource') if n.get('xs.id')]
    assert set(mesh_ids) == {n.get('xs.id') for n in old_root.iter('CArtMeshSource') if n.get('xs.id')}
    for ref in mesh_ids:
        mesh = ids[ref]
        assert canonical(old_ids[ref], True) == canonical(mesh, True), 'Geometry/poses changed: '+ref
        resource, pixels = source_points(mesh, ids)
        ext_ref = named(mesh, 'CTextureInputExtension', 'textureInputExtension').get('xs.ref') if any(n.get('xs.n') == 'textureInputExtension' for n in mesh.iter('CTextureInputExtension')) else next(n.get('xs.ref') for n in mesh.iter('CTextureInputExtension'))
        extension = ids[ext_ref]
        current = ids[named(extension, 'CTextureInput_ModelImage', 'currentTextureInputData').get('xs.ref')]
        image_ref = named(current, 'CModelImageGuid', '_modelImageGuid').get('xs.ref')
        guid, offset, atlas_affine = placements[image_ref]
        region = next(extension.iter('CTextureInput_TextureAtlasRegion'))
        assert named(region, 'CTextureAtlasGuid', 'textureAtlasGuid').get('xs.ref') == guid
        input_affine = matrix(named(region, 'CAffine', 'inputImageLocalToCanvasTransform'))
        assert np.allclose(input_affine, atlas_affine, atol=1e-8, rtol=0)
        source_affine = matrix(named(images[image_ref], 'CAffine', '_materialLocalToCanvasTransform'))
        for input_node in (current, region):
            assert np.array_equal(matrix(named(input_node, 'CAffine', 'optionalTransformOnCanvas')), np.eye(3)), 'Nonidentity input needs handling'
        atlas_pixels = transform(transform(pixels, source_affine), np.linalg.inv(input_affine))
        mapping_error = float(np.max(np.abs(atlas_pixels - pixels - offset)))
        assert mapping_error < .001, ('Mapping drift', ref, mapping_error)
        resource_ref = resource.get('xs.id')
        if resource_ref not in cached:
            cached[resource_ref] = raster(archive, resource)
        image = cached[resource_ref]
        x, y = offset.astype(int)
        assert np.array_equal(offset, [x, y]), 'Noninteger placement'
        assert np.array_equal(image, pages[guid][y:y+image.shape[0], x:x+image.shape[1]]), 'Overwritten pixels'
        error = float(np.max(np.abs(sample(image, pixels) - sample(pages[guid], atlas_pixels))))
        assert error < .02, ('Sampling drift or texture bleed', ref, error)
        old_resource, old_pixels = source_points(old_ids[ref], old_ids)
        old_image = raster(old_archive, old_resource)
        source_error = float(np.max(np.abs(sample(old_image, old_pixels) - sample(image, pixels))))
        assert source_error < .1, ('Source crop changed sample', ref, source_error)
        rows.append({'mesh':ref, 'atlas_mapping_error_px':mapping_error, 'atlas_rgba_sample_error':error, 'source_rgba_sample_error':source_error})
    for node in old_root.iter():
        if node.get('xs.id') and node.tag in ('CWarpDeformerSource', 'CRotationDeformerSource', 'CParameter'):
            assert canonical(node) == canonical(ids[node.get('xs.id')]), 'Rig changed'
    for entry in old_archive.entries:
        if entry.path != 'main.xml':
            assert old_archive.read_unique_path(entry.path, 256*1024*1024) == archive.read_unique_path(entry.path, 256*1024*1024)
    return {'source_sha256':hashlib.sha256(old_data).hexdigest(), 'output_sha256':hashlib.sha256(data).hexdigest(), 'meshes_checked':len(rows), 'atlas_count':len(pages), 'image_placements':len(placements), 'checks':rows, 'native_validated':False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('candidate', type=Path)
    a = p.parse_args()
    print(json.dumps(check(a.source, a.candidate), indent=2))
