"""Krita-native, copy-on-write art builder for Jade r21.

This module is executed by ``kritarunner`` inside Krita's own Python runtime.
It never opens or writes the immutable v004 source.  The first functional pass
adds properly separated r21 facial art to the versioned v005 working KRA.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PyQt5.QtCore import QByteArray, QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from krita import Krita


Application = Krita.instance()


CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 4160


def _runner_args(args):
    """Accept both direct Python calls and kritarunner's single argv list."""

    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return tuple(args[0])
    return tuple(args)


def smoke(*args):
    """Emit a deterministic runner probe without touching a document."""

    args = _runner_args(args)
    payload = {"status": "ok", "args": list(args), "krita": Application.version()}
    if args:
        Path(str(args[0])).resolve().write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload))
    return 0


def _rgba_layer(document, name: str, image: QImage, parent, above=None):
    """Create one full-canvas RGBA paint layer from a premultiplied QImage."""

    if image.width() != CANVAS_WIDTH or image.height() != CANVAS_HEIGHT:
        raise RuntimeError(f"{name}: wrong canvas size")
    layer = document.createNode(name, "paintlayer")
    # Krita's U8 RGBA pixel API expects BGRA byte order on little-endian hosts.
    converted = image.convertToFormat(QImage.Format_ARGB32)
    payload = QByteArray(converted.constBits().asstring(converted.byteCount()))
    layer.setPixelData(payload, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
    parent.addChildNode(layer, above)
    return layer


def _rgba_layer_region(document, name, image, x, y, parent, above=None):
    """Create a sparse paint layer from one BGRA region."""

    layer = document.createNode(name, "paintlayer")
    converted = image.convertToFormat(QImage.Format_ARGB32)
    payload = QByteArray(converted.constBits().asstring(converted.byteCount()))
    layer.setPixelData(payload, int(x), int(y), image.width(), image.height())
    parent.addChildNode(layer, above)
    return layer


def _transparent_canvas():
    image = QImage(CANVAS_WIDTH, CANVAS_HEIGHT, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    return image


def _draw_path_layer(name, path, color, width, *, fill=None):
    image = _transparent_canvas()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    if fill is None:
        painter.setBrush(Qt.NoBrush)
    else:
        painter.setBrush(QColor(*fill))
    pen = QPen(QColor(*color))
    pen.setWidthF(float(width))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(path)
    painter.end()
    return name, image


def _face_volume_overlay():
    """Subtle warm/cool sculpting that stays inside Jade's face silhouette."""

    image = _transparent_canvas()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # Side planes and jaw shadow: restrained, semi-transparent cel shapes.
    shadow = QColor(157, 93, 101, 14)
    left = QPainterPath(QPointF(1448, 704))
    left.cubicTo(1445, 850, 1480, 1030, 1602, 1135)
    left.cubicTo(1550, 1115, 1500, 1060, 1474, 978)
    left.cubicTo(1442, 878, 1438, 780, 1448, 704)
    painter.fillPath(left, shadow)
    right = QPainterPath(QPointF(2058, 700))
    right.cubicTo(2064, 850, 2028, 1035, 1908, 1138)
    right.cubicTo(1960, 1115, 2005, 1060, 2033, 977)
    right.cubicTo(2065, 875, 2068, 780, 2058, 700)
    painter.fillPath(right, shadow)

    # Cheek warmth uses radial falloff; no hard circular patches.
    painter.setPen(Qt.NoPen)
    for cx in (1593.0, 1917.0):
        gradient = QRadialGradient(QPointF(cx, 982.0), 112.0)
        gradient.setColorAt(0.0, QColor(239, 124, 143, 19))
        gradient.setColorAt(0.48, QColor(239, 124, 143, 10))
        gradient.setColorAt(1.0, QColor(239, 124, 143, 0))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QRectF(cx - 112.0, 934.0, 224.0, 96.0))

    # Lower-face/chin volume.
    chin = QRadialGradient(QPointF(1755.0, 1114.0), 128.0)
    chin.setColorAt(0.0, QColor(132, 88, 102, 10))
    chin.setColorAt(1.0, QColor(132, 88, 102, 0))
    painter.setBrush(QBrush(chin))
    painter.drawEllipse(QRectF(1627, 1080, 256, 70))

    # Nose and cheek highlights.
    painter.setBrush(QColor(255, 248, 240, 26))
    painter.drawEllipse(QRectF(1737, 925, 35, 58))
    painter.drawEllipse(QRectF(1550, 934, 96, 32))
    painter.drawEllipse(QRectF(1865, 934, 96, 32))
    painter.end()
    return image


def _brow_layers():
    layers = []
    ink = (47, 69, 48, 235)
    for side, x0, x1, lift in (("R", 1482, 1652, 0), ("L", 1848, 2018, -2)):
        path = QPainterPath(QPointF(x0, 744 + lift))
        path.cubicTo(x0 + 47, 718 + lift, x1 - 51, 718 + lift, x1, 742 + lift)
        layers.append(_draw_path_layer(f"JAD_BROW_{side}_R21", path, ink, 12.0))
    return layers


def _mouth_layers():
    """Neutral professional mouth components, separated for later Live2D rig."""

    cx, cy = 1748.0, 1062.0
    ink = (115, 68, 75, 230)
    soft = (194, 114, 124, 135)
    layers = []

    upper = QPainterPath(QPointF(cx - 48, cy - 1))
    upper.cubicTo(cx - 24, cy + 4, cx - 11, cy + 8, cx, cy + 8)
    upper.cubicTo(cx + 11, cy + 8, cx + 24, cy + 4, cx + 48, cy - 1)
    layers.append(_draw_path_layer("JAD_MOUTH_LINE_UPPER_R21", upper, ink, 5.2))

    lower = QPainterPath(QPointF(cx - 18, cy + 19))
    lower.cubicTo(cx - 7, cy + 22, cx + 7, cy + 22, cx + 18, cy + 19)
    layers.append(_draw_path_layer("JAD_MOUTH_LINE_LOWER_R21", lower, soft, 3.0))

    for side, x, direction in (("R", cx - 48, -1.0), ("L", cx + 48, 1.0)):
        corner = QPainterPath(QPointF(x, cy - 1))
        corner.cubicTo(x + 3 * direction, cy - 3, x + 6 * direction, cy - 2, x + 8 * direction, cy + 1)
        layers.append(_draw_path_layer(f"JAD_MOUTH_CORNER_{side}_R21", corner, ink, 4.2))

    # Invisible-at-neutral components remain real separated art ready for
    # MouthOpen keyforms; they are created hidden by build_face_pass.
    interior = QPainterPath(QPointF(cx - 57, cy + 1))
    interior.cubicTo(cx - 40, cy - 8, cx + 40, cy - 8, cx + 57, cy + 1)
    interior.cubicTo(cx + 43, cy + 56, cx - 43, cy + 56, cx - 57, cy + 1)
    layers.append(_draw_path_layer("JAD_MOUTH_INTERIOR_R21", interior, (76, 37, 47, 255), 1.0, fill=(76, 37, 47, 255)))

    teeth = QPainterPath(QPointF(cx - 46, cy + 3))
    teeth.cubicTo(cx - 20, cy - 3, cx + 20, cy - 3, cx + 46, cy + 3)
    teeth.cubicTo(cx + 30, cy + 19, cx - 30, cy + 19, cx - 46, cy + 3)
    layers.append(_draw_path_layer("JAD_MOUTH_TEETH_UPPER_R21", teeth, (234, 226, 216, 255), 1.0, fill=(255, 250, 244, 255)))

    tongue = QPainterPath(QPointF(cx - 37, cy + 34))
    tongue.cubicTo(cx - 18, cy + 22, cx + 18, cy + 22, cx + 37, cy + 34)
    tongue.cubicTo(cx + 22, cy + 54, cx - 22, cy + 54, cx - 37, cy + 34)
    layers.append(_draw_path_layer("JAD_MOUTH_TONGUE_R21", tongue, (193, 91, 113, 255), 1.0, fill=(226, 124, 143, 255)))
    return layers


def _find_node(root, name):
    stack = [root]
    matches = []
    while stack:
        node = stack.pop()
        if node.name() == name:
            matches.append(node)
        stack.extend(node.childNodes())
    if len(matches) != 1:
        raise RuntimeError(f"{name}: expected one node, found {len(matches)}")
    return matches[0]


HAIR_BACK_SPECS = {
    "JAD_HAIR_BACK_C": ((1500, 241, 2131, 1690), 3),
    "JAD_HAIR_BACK_R_OUTER": ((948, 313, 1542, 1633), 3),
    "JAD_HAIR_BACK_L_OUTER": ((2062, 397, 2565, 1682), 3),
    "JAD_HAIR_BACK_R_INNER": ((1220, 247, 1713, 1639), 2),
    "JAD_HAIR_BACK_L_INNER": ((1816, 248, 2411, 1696), 2),
}

HAIR_FRONT_SPECS = {
    "JAD_HAIR_TEMPLE_R": (1376, 811, 1674, 1491),
    "JAD_HAIR_TEMPLE_L": (1896, 771, 2159, 1519),
    "JAD_HAIR_BANG_R_OUTER": (1268, 296, 1636, 1016),
    "JAD_HAIR_BANG_L_OUTER": (1920, 295, 2241, 1031),
    "JAD_HAIR_BANG_R_INNER": (1533, 258, 1756, 1005),
    "JAD_HAIR_BANG_L_INNER": (1782, 268, 2056, 1032),
    "JAD_HAIR_BANG_C": (1657, 254, 1881, 844),
    "JAD_HAIR_AHOGE": (1528, 95, 1809, 334),
}


def _node_region(node, bbox):
    left, top, right, bottom = bbox
    width, height = right - left, bottom - top
    pixels = node.pixelData(left, top, width, height)
    return QImage(pixels, width, height, QImage.Format_ARGB32).copy()


def _hair_segment(source, index, count):
    """Make one overlapping, shaded, complete-looking hair-lock region."""

    width, height = source.width(), source.height()
    overlap = 0.065
    band = 1.0 / count
    centre_offset = (index - (count - 1) / 2.0) * 0.025
    left_top = max(0.0, (index * band - overlap) * width)
    right_top = min(float(width), ((index + 1) * band + overlap) * width)
    left_bottom = max(0.0, left_top + centre_offset * width)
    right_bottom = min(float(width), right_top + centre_offset * width)

    clip = QPainterPath(QPointF(left_top, 0.0))
    clip.lineTo(QPointF(right_top, 0.0))
    clip.cubicTo(
        QPointF(right_top + centre_offset * width * 0.3, height * 0.35),
        QPointF(right_bottom - centre_offset * width * 0.2, height * 0.72),
        QPointF(right_bottom, float(height)),
    )
    clip.lineTo(QPointF(left_bottom, float(height)))
    clip.cubicTo(
        QPointF(left_bottom - centre_offset * width * 0.2, height * 0.72),
        QPointF(left_top + centre_offset * width * 0.3, height * 0.35),
        QPointF(left_top, 0.0),
    )
    clip.closeSubpath()

    result = QImage(width, height, QImage.Format_ARGB32)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setClipPath(clip)
    painter.drawImage(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)

    # Contact shade gives the lock an underside instead of a flat cut-out.
    shade = QRadialGradient(
        QPointF((left_top + right_top) * 0.5, height * 0.22),
        max(width * 0.48, height * 0.34),
    )
    shade.setColorAt(0.0, QColor(30, 68, 58, 8))
    shade.setColorAt(0.62, QColor(27, 61, 53, 18))
    shade.setColorAt(1.0, QColor(23, 54, 48, 34))
    painter.fillPath(clip, QBrush(shade))

    # Each lock has a restrained directional highlight of its own.
    centre_top = (left_top + right_top) * 0.5
    centre_bottom = (left_bottom + right_bottom) * 0.5
    highlight = QPainterPath(QPointF(centre_top - width * 0.035, height * 0.16))
    highlight.cubicTo(
        QPointF(centre_top + width * 0.05, height * 0.34),
        QPointF(centre_bottom - width * 0.08, height * 0.61),
        QPointF(centre_bottom - width * 0.03, height * 0.79),
    )
    pen = QPen(QColor(205, 235, 170, 38))
    pen.setWidthF(max(7.0, width / count * 0.065))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(highlight)
    painter.end()
    return result


def _enhance_front_lock(source, seed):
    width, height = source.width(), source.height()
    result = source.copy()
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)

    depth = QRadialGradient(QPointF(width * (0.42 + 0.03 * (seed % 3)), height * 0.18), max(width, height) * 0.82)
    depth.setColorAt(0.0, QColor(21, 57, 47, 5))
    depth.setColorAt(0.68, QColor(22, 59, 49, 14))
    depth.setColorAt(1.0, QColor(16, 48, 42, 28))
    painter.fillRect(QRectF(0, 0, width, height), QBrush(depth))

    highlight = QPainterPath(QPointF(width * 0.46, height * 0.13))
    highlight.cubicTo(
        QPointF(width * 0.56, height * 0.30),
        QPointF(width * 0.38, height * 0.55),
        QPointF(width * 0.48, height * 0.76),
    )
    pen = QPen(QColor(218, 241, 181, 34))
    pen.setWidthF(max(6.0, width * 0.032))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(highlight)
    painter.end()
    return result


def build_hair_pass(*args):
    """Replace five rear masses with 13 source locks and polish front locks."""

    args = _runner_args(args)
    if len(args) != 3:
        raise RuntimeError("build_hair_pass requires input_kra output_kra report_json")
    source, output, report = map(lambda value: Path(str(value)).resolve(), args)
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        root = document.rootNode()
        back_parent = _find_node(root, "JAD_GRP_HAIR_BACK")
        front_parent = _find_node(root, "JAD_GRP_HAIR_FRONT")
        back_group = document.createGroupLayer("R21_HAIR_BACK_LOCKS_V1")
        back_parent.addChildNode(back_group, None)
        front_group = document.createGroupLayer("R21_HAIR_FRONT_LOCKS_V1")
        front_parent.addChildNode(front_group, None)

        created_back = []
        created_front = []
        hidden = []
        back_above = None
        for source_name, (bbox, count) in HAIR_BACK_SPECS.items():
            node = _find_node(root, source_name)
            source_image = _node_region(node, bbox)
            left, top, _right, _bottom = bbox
            for index in range(count):
                name = f"{source_name}_R21_LOCK_{index + 1:02d}"
                segment = _hair_segment(source_image, index, count)
                back_above = _rgba_layer_region(
                    document, name, segment, left, top, back_group, back_above
                )
                created_back.append(name)
            node.setVisible(False)
            hidden.append(source_name)

        front_above = None
        for seed, (source_name, bbox) in enumerate(HAIR_FRONT_SPECS.items()):
            node = _find_node(root, source_name)
            source_image = _node_region(node, bbox)
            enhanced = _enhance_front_lock(source_image, seed)
            left, top, _right, _bottom = bbox
            name = f"{source_name}_R21"
            front_above = _rgba_layer_region(
                document, name, enhanced, left, top, front_group, front_above
            )
            created_front.append(name)
            node.setVisible(False)
            hidden.append(source_name)

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita exportImage failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-hair-pass.v1",
            "status": "ok",
            "source": str(source),
            "output": str(output),
            "rear_lock_count": len(created_back),
            "front_lock_count": len(created_front),
            "total_independent_hair_layers": len(created_back) + len(created_front),
            "created_rear": created_back,
            "created_front": created_front,
            "hidden_legacy_nodes": hidden,
            "contract": {
                "rear_overlap_fraction": 0.065,
                "per_lock_depth": True,
                "per_lock_highlight": True,
                "original_nodes_deleted": False,
            },
        }
        report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


def export_preview(*args):
    """Export the visible composite of one KRA to a non-overwriting PNG."""

    args = _runner_args(args)
    if len(args) != 2:
        raise RuntimeError("export_preview requires source_kra output_png")
    source, output = map(lambda value: Path(str(value)).resolve(), args)
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if output.exists():
        raise RuntimeError(f"output exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita PNG export failed")
        document.waitForDone()
    finally:
        document.close()
    print(json.dumps({"status": "ok", "source": str(source), "output": str(output)}))
    return 0


def build_face_pass(*args):
    """Add the first functional r21 face/mouth pass to a v005 KRA copy.

    Args: input_kra, output_kra, report_json.
    """

    args = _runner_args(args)
    if len(args) != 3:
        raise RuntimeError("build_face_pass requires input_kra output_kra report_json")
    source, output, report = map(lambda value: Path(str(value)).resolve(), args)
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        if document.width() != CANVAS_WIDTH or document.height() != CANVAS_HEIGHT:
            raise RuntimeError("unexpected source canvas")
        root = document.rootNode()
        rig_parts = _find_node(root, "RIG_PARTS")
        face_group = _find_node(root, "JAD_GRP_FACE")

        r21 = document.createGroupLayer("R21_FACE_RECONSTRUCTION_V1")
        face_group.addChildNode(r21, None)

        volume = _rgba_layer(document, "JAD_FACE_VOLUME_R21", _face_volume_overlay(), r21)
        created = [volume.name()]
        above = volume
        for name, image in _brow_layers():
            above = _rgba_layer(document, name, image, r21, above)
            created.append(name)

        mouth_group = document.createGroupLayer("JAD_GRP_MOUTH_R21")
        r21.addChildNode(mouth_group, above)
        created.append(mouth_group.name())
        inner_names = {"JAD_MOUTH_INTERIOR_R21", "JAD_MOUTH_TEETH_UPPER_R21", "JAD_MOUTH_TONGUE_R21"}
        mouth_above = None
        for name, image in _mouth_layers():
            mouth_above = _rgba_layer(document, name, image, mouth_group, mouth_above)
            if name in inner_names:
                mouth_above.setVisible(False)
            created.append(name)

        # Preserve the original art but remove its duplicate neutral mouth and
        # brows from the visible v005 composite.  Nothing is deleted.
        hidden = []
        for old_name in (
            "JAD_BROW_L", "JAD_BROW_R", "JAD_MOUTH_CORNER_L",
            "JAD_MOUTH_CORNER_R", "JAD_MOUTH_INTERIOR",
            "JAD_MOUTH_LINE_LOWER", "JAD_MOUTH_LINE_UPPER",
            "JAD_MOUTH_TEETH_LOWER", "JAD_MOUTH_TONGUE",
        ):
            node = _find_node(root, old_name)
            node.setVisible(False)
            hidden.append(old_name)

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita exportImage failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-face-pass.v1",
            "status": "ok",
            "source": str(source),
            "output": str(output),
            "canvas": [document.width(), document.height()],
            "created_nodes": created,
            "hidden_legacy_nodes": hidden,
            "preserved": ["JAD_EYE_*", "JAD_EYE_*_CLOSED_*", "all original pixels and nodes"],
        }
        report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


MASTER_V3_LAYER_ORDER = (
    ("JAD_R21_RESIDUAL.png", "JAD_R21_RESIDUAL_UNDERLAY"),
    ("JAD_R21_HAIR.png", "JAD_R21_HAIR_PAINTED_MASTER"),
    ("JAD_R21_DRESS.png", "JAD_R21_DRESS_PAINTED_MASTER"),
    ("JAD_R21_SKIN.png", "JAD_R21_SKIN_PAINTED_MASTER"),
    ("JAD_R21_EARS.png", "JAD_R21_EARS_NORMAL_PAINTED_MASTER"),
    ("JAD_R21_EYE_L.png", "JAD_R21_EYE_L_OPEN_PAINTED_MASTER"),
    ("JAD_R21_EYE_R.png", "JAD_R21_EYE_R_OPEN_PAINTED_MASTER"),
    ("JAD_R21_BROW_L.png", "JAD_R21_BROW_L_PAINTED_MASTER"),
    ("JAD_R21_BROW_R.png", "JAD_R21_BROW_R_PAINTED_MASTER"),
    ("JAD_R21_MOUTH.png", "JAD_R21_MOUTH_NEUTRAL_PAINTED_MASTER"),
)


def build_master_v3_import(*args):
    """Import the approved painted r21 master as preserved semantic layers.

    Args: input_kra, semantic_layer_directory, output_kra, report_json.
    The legacy RIG_PARTS tree is hidden, never deleted, so this remains a
    copy-on-write art-source milestone rather than a destructive replacement.
    """

    args = _runner_args(args)
    if len(args) != 4:
        raise RuntimeError(
            "build_master_v3_import requires input_kra layer_dir output_kra report_json"
        )
    source, layer_dir, output, report = map(
        lambda value: Path(str(value)).resolve(), args
    )
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if not layer_dir.is_dir():
        raise RuntimeError(f"semantic layer directory missing: {layer_dir}")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    missing = [name for name, _node in MASTER_V3_LAYER_ORDER if not (layer_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"semantic layers missing: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        if document.width() != CANVAS_WIDTH or document.height() != CANVAS_HEIGHT:
            raise RuntimeError("unexpected source canvas")
        root = document.rootNode()
        legacy = _find_node(root, "RIG_PARTS")
        legacy.setVisible(False)

        master_group = document.createGroupLayer("R21_MASTER_V3_PAINTED_SEMANTIC")
        root.addChildNode(master_group, None)
        created = []
        above = None
        for filename, node_name in MASTER_V3_LAYER_ORDER:
            image = QImage(str(layer_dir / filename))
            if image.isNull():
                raise RuntimeError(f"Krita failed to load {filename}")
            if image.width() != CANVAS_WIDTH or image.height() != CANVAS_HEIGHT:
                raise RuntimeError(f"{filename}: unexpected dimensions")
            above = _rgba_layer(document, node_name, image, master_group, above)
            created.append(node_name)
            del image

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita KRA export failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-master-v3-import.v1",
            "status": "ok",
            "source": str(source),
            "semantic_layer_directory": str(layer_dir),
            "output": str(output),
            "canvas": [document.width(), document.height()],
            "group": master_group.name(),
            "created_nodes_bottom_to_top": created,
            "hidden_legacy_group": legacy.name(),
            "deleted_nodes": [],
            "next": "split painted master into rig-ready hair, face, arms and dress locks",
        }
        report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


def build_rig_layer_import(*args):
    """Import cropped r21 rig-art layers from a deterministic manifest.

    Args: semantic_master_kra, manifest_json, output_kra, report_json.
    The semantic master group is hidden but retained as a neutral-reference and
    rollback source. No prior pixel node is deleted.
    """

    args = _runner_args(args)
    if len(args) != 4:
        raise RuntimeError(
            "build_rig_layer_import requires source_kra manifest_json output_kra report_json"
        )
    source, manifest_path, output, report = map(
        lambda value: Path(str(value)).resolve(), args
    )
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if not manifest_path.is_file():
        raise RuntimeError(f"manifest missing: {manifest_path}")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "jade.r21.rig-art-layers.v1":
        raise RuntimeError("unsupported rig-art manifest")
    if manifest.get("canvas") != [CANVAS_WIDTH, CANVAS_HEIGHT]:
        raise RuntimeError("rig-art manifest canvas mismatch")

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        root = document.rootNode()
        semantic_master = _find_node(root, "R21_MASTER_V3_PAINTED_SEMANTIC")
        semantic_master.setVisible(False)

        rig_root = document.createGroupLayer("R21_RIG_ART_V1")
        root.addChildNode(rig_root, None)
        group_nodes = {}
        group_above = None
        for group_name in manifest["groups_bottom_to_top"]:
            group = document.createGroupLayer(group_name)
            rig_root.addChildNode(group, group_above)
            group_nodes[group_name] = group
            group_above = group

        created = []
        layer_above = {name: None for name in group_nodes}
        for item in sorted(manifest["layers"], key=lambda entry: (entry["z"], entry["name"])):
            group_name = item["group"]
            if group_name not in group_nodes:
                raise RuntimeError(f"unknown group in manifest: {group_name}")
            image_path = Path(item["file"]).resolve()
            if not image_path.is_file():
                raise RuntimeError(f"rig-art layer missing: {image_path}")
            image = QImage(str(image_path))
            if image.isNull():
                raise RuntimeError(f"Krita failed to load {image_path}")
            if image.width() != int(item["width"]) or image.height() != int(item["height"]):
                raise RuntimeError(f"rig-art layer dimensions mismatch: {item['name']}")
            layer = _rgba_layer_region(
                document,
                item["name"],
                image,
                int(item["x"]),
                int(item["y"]),
                group_nodes[group_name],
                layer_above[group_name],
            )
            layer_above[group_name] = layer
            created.append(item["name"])
            del image

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita rig-art KRA export failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-rig-art-import.v1",
            "status": "ok",
            "source": str(source),
            "manifest": str(manifest_path),
            "output": str(output),
            "root_group": rig_root.name(),
            "groups_bottom_to_top": manifest["groups_bottom_to_top"],
            "created_layer_count": len(created),
            "created_layers": created,
            "hidden_semantic_reference": semantic_master.name(),
            "deleted_nodes": [],
        }
        report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


def build_eye_endpoint_import(*args):
    """Append true closed-eye and socket art to the r21 rig-art KRA.

    Args: rig_art_kra, eye_manifest_json, output_kra, report_json.
    Socket layers are visible beneath the open eyes. True closed-eye sprites
    are imported hidden and are intended to fade in only near EyeOpen=0.
    """

    args = _runner_args(args)
    if len(args) != 4:
        raise RuntimeError(
            "build_eye_endpoint_import requires source_kra eye_manifest output_kra report_json"
        )
    source, manifest_path, output, report = map(
        lambda value: Path(str(value)).resolve(), args
    )
    if not source.is_file() or not manifest_path.is_file():
        raise RuntimeError("source KRA or eye manifest missing")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "jade.r21.eye-endpoint-art.v1":
        raise RuntimeError("unsupported eye endpoint manifest")

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        root = document.rootNode()
        _find_node(root, "R21_RIG_ART_V1")
        groups = {
            "30_SKIN": _find_node(root, "30_SKIN"),
            "50_FACE_FEATURES": _find_node(root, "50_FACE_FEATURES"),
        }
        anchors = {
            "30_SKIN": _find_node(root, "JAD_R21_FACE_SKIN"),
            "50_FACE_FEATURES_L": _find_node(root, "JAD_R21_EYE_L_OPEN_MASTER"),
            "50_FACE_FEATURES_R": _find_node(root, "JAD_R21_EYE_R_OPEN_MASTER"),
        }
        created = []
        visible = []
        hidden = []
        skin_anchor = anchors["30_SKIN"]
        for item in sorted(manifest["layers"], key=lambda entry: (entry["z"], entry["name"])):
            group_name = item["group"]
            if group_name not in groups:
                raise RuntimeError(f"unsupported eye art group: {group_name}")
            image_path = Path(item["file"]).resolve()
            image = QImage(str(image_path))
            if image.isNull():
                raise RuntimeError(f"Krita failed to load {image_path}")
            if group_name == "30_SKIN":
                anchor = skin_anchor
            else:
                side = "L" if "_L_" in item["name"] else "R"
                anchor = anchors[f"50_FACE_FEATURES_{side}"]
            layer = _rgba_layer_region(
                document,
                item["name"],
                image,
                int(item["x"]),
                int(item["y"]),
                groups[group_name],
                anchor,
            )
            if item["role"] == "true_closed_eye_endpoint":
                layer.setVisible(False)
                hidden.append(item["name"])
            else:
                visible.append(item["name"])
                skin_anchor = layer
            created.append(item["name"])
            del image

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita eye-endpoint KRA export failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-eye-endpoint-import.v1",
            "status": "ok",
            "source": str(source),
            "manifest": str(manifest_path),
            "output": str(output),
            "created_layers": created,
            "visible_socket_layers": visible,
            "hidden_closed_endpoint_layers": hidden,
            "eye_open_contract": manifest["method"],
            "deleted_nodes": [],
        }
        report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


def build_mouth_endpoint_import(*args):
    """Append neutral/open speaking-mouth art to an r21 rig-art KRA.

    Args: rig_art_kra, mouth_manifest_json, output_kra, report_json.
    The broad semantic neutral mouth is hidden and replaced by the clean
    painted line. Open components remain hidden until Cubism drives MouthOpenY.
    """

    args = _runner_args(args)
    if len(args) != 4:
        raise RuntimeError(
            "build_mouth_endpoint_import requires source_kra mouth_manifest output_kra report_json"
        )
    source, manifest_path, output, report = map(
        lambda value: Path(str(value)).resolve(), args
    )
    if not source.is_file() or not manifest_path.is_file():
        raise RuntimeError("source KRA or mouth manifest missing")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "jade.r21.mouth-endpoint-art.v1":
        raise RuntimeError("unsupported mouth endpoint manifest")

    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        root = document.rootNode()
        skin_group = _find_node(root, "30_SKIN")
        face_group = _find_node(root, "50_FACE_FEATURES")
        old_neutral = _find_node(root, "JAD_R21_MOUTH_NEUTRAL_MASTER")
        # The first semantic colour pass misclassified a jaw/neck edge patch as
        # mouth art.  It contains no neutral smile and must remain visible or a
        # one-column seam appears below the viewer-left jaw.
        old_neutral.setName("JAD_R21_JAW_NECK_EDGE_PATCH")
        old_neutral.setVisible(True)
        skin_anchor = _find_node(root, "JAD_R21_FACE_SKIN")
        face_anchor = old_neutral
        created = []
        visible = []
        hidden = []
        for item in sorted(manifest["layers"], key=lambda entry: (entry["z"], entry["name"])):
            group = skin_group if item["group"] == "30_SKIN" else face_group
            anchor = skin_anchor if item["group"] == "30_SKIN" else face_anchor
            image_path = Path(item["file"]).resolve()
            image = QImage(str(image_path))
            if image.isNull():
                raise RuntimeError(f"Krita failed to load {image_path}")
            # Krita 4.4 can leave a one-column artefact when a very sparse,
            # antialiased mouth PNG is injected through setPixelData at a
            # non-zero region offset.  Assemble it on a transparent full
            # canvas first, then use the stable full-canvas import path.
            canvas_image = _transparent_canvas()
            painter = QPainter(canvas_image)
            painter.drawImage(int(item["x"]), int(item["y"]), image)
            painter.end()
            layer = _rgba_layer(
                document,
                item["name"],
                canvas_image,
                group,
                anchor,
            )
            if item["role"].startswith("mouth_open_"):
                layer.setVisible(False)
                hidden.append(item["name"])
            else:
                visible.append(item["name"])
            if item["group"] == "30_SKIN":
                skin_anchor = layer
            else:
                face_anchor = layer
            created.append(item["name"])
            del canvas_image
            del image

        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita mouth-endpoint KRA export failed")
        document.waitForDone()
        payload = {
            "schema": "jade.r21.krita-mouth-endpoint-import.v1",
            "status": "ok",
            "source": str(source),
            "manifest": str(manifest_path),
            "output": str(output),
            "preserved_jaw_neck_patch": old_neutral.name(),
            "created_layers": created,
            "visible_neutral_layers": visible,
            "hidden_open_layers": hidden,
            "mouth_contract": manifest["method"],
            "deleted_nodes": [],
        }
        report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0


def inspect_node_api(*args):
    """Write the available Krita Node API and top-level tree for diagnostics."""

    args = _runner_args(args)
    if len(args) != 2:
        raise RuntimeError("inspect_node_api requires source_kra report_json")
    source, report = map(lambda value: Path(str(value)).resolve(), args)
    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        root = document.rootNode()
        payload = {
            "root_methods": sorted(name for name in dir(root) if not name.startswith("_")),
            "children": [
                {"name": node.name(), "type": node.type(), "visible": node.visible()}
                for node in root.childNodes()
            ],
        }
        report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    finally:
        document.close()
    return 0


def export_interchange_psd(*args):
    """Export a versioned layered KRA checkpoint as Cubism interchange PSD.

    Args: source_kra, output_psd, report_json.
    """

    args = _runner_args(args)
    if len(args) != 3:
        raise RuntimeError("export_interchange_psd requires source_kra output_psd report_json")
    source, output, report = map(lambda value: Path(str(value)).resolve(), args)
    if not source.is_file():
        raise RuntimeError(f"source missing: {source}")
    if output.exists() or report.exists():
        raise RuntimeError("output/report exists; refusing overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    document = Application.openDocument(str(source))
    if document is None:
        raise RuntimeError(f"Krita failed to open {source}")
    try:
        if document.width() != CANVAS_WIDTH or document.height() != CANVAS_HEIGHT:
            raise RuntimeError("unexpected source canvas")
        root = document.rootNode()
        rig_root = _find_node(root, "R21_RIG_ART_V1")
        rig_root.setVisible(True)
        removed_reference_groups = []
        for node in list(root.childNodes()):
            if node.name() == rig_root.name():
                continue
            removed_reference_groups.append(node.name())
            root.removeChildNode(node)
        document.refreshProjection()
        if not document.exportImage(str(output), __import__("krita").InfoObject()):
            raise RuntimeError("Krita layered PSD export failed")
        document.waitForDone()
        if not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError("Krita did not produce a valid PSD")
        payload = {
            "schema": "jade.r21.krita-interchange-psd.v1",
            "status": "ok",
            "source": str(source),
            "output": str(output),
            "canvas": [document.width(), document.height()],
            "output_bytes": output.stat().st_size,
            "copy_on_write": True,
            "export_root": rig_root.name(),
            "stripped_reference_groups": removed_reference_groups,
        }
        report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        document.close()
    return 0
