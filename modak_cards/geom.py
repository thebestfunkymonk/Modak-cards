"""Vector geometry on top of skia-pathops: primitives, booleans, offsets, SVG output."""
from __future__ import annotations

import math

import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from pathops import LineCap, LineJoin, OpBuilder, Path, PathOp

KAPPA = 0.5522847498


def _num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def d(path: Path) -> str:
    pen = SVGPathPen(None, ntos=_num)
    path.draw(pen)
    return pen.getCommands()


def circle(cx: float, cy: float, r: float) -> Path:
    k = KAPPA * r
    p = Path()
    p.moveTo(cx + r, cy)
    p.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    p.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    p.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    p.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    p.close()
    return p


def poly(points) -> Path:
    p = Path()
    p.moveTo(*points[0])
    for pt in points[1:]:
        p.lineTo(*pt)
    p.close()
    return p


def rect(x: float, y: float, w: float, h: float) -> Path:
    return poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def rrect(x: float, y: float, w: float, h: float, r: float) -> Path:
    r = min(r, w / 2, h / 2)
    k = KAPPA * r
    p = Path()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.cubicTo(x + w - r + k, y, x + w, y + r - k, x + w, y + r)
    p.lineTo(x + w, y + h - r)
    p.cubicTo(x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h)
    p.lineTo(x + r, y + h)
    p.cubicTo(x + r - k, y + h, x, y + h - r + k, x, y + h - r)
    p.lineTo(x, y + r)
    p.cubicTo(x, y + r - k, x + r - k, y, x + r, y)
    p.close()
    return p


def move(p: Path, dx: float, dy: float) -> Path:
    return p.transform(1, 0, 0, 1, dx, dy)


def affine(p: Path, a, b, c, dd, e, f) -> Path:
    return p.transform(a, b, c, dd, e, f)


def rotate180(p: Path, cx: float, cy: float) -> Path:
    return p.transform(-1, 0, 0, -1, 2 * cx, 2 * cy)


def scale_about(p: Path, s: float, cx: float, cy: float) -> Path:
    return p.transform(s, 0, 0, s, cx - s * cx, cy - s * cy)


def union(*paths: Path) -> Path:
    b = OpBuilder()
    for p in paths:
        b.add(p, PathOp.UNION)
    return b.resolve()


def diff(a: Path, b: Path) -> Path:
    return pathops.op(a, b, PathOp.DIFFERENCE)


def inter(a: Path, b: Path) -> Path:
    return pathops.op(a, b, PathOp.INTERSECTION)


def stroke_outline(p: Path, width: float) -> Path:
    """The filled region covered by stroking `p` with round joins."""
    s = Path()
    s.addPath(p)
    s.stroke(width, LineCap.ROUND_CAP, LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads()
    return pathops.simplify(s)


def outset(p: Path, r: float) -> Path:
    return union(p, stroke_outline(p, 2 * r)) if r > 0 else p


def inset(p: Path, r: float) -> Path:
    return diff(p, stroke_outline(p, 2 * r)) if r > 0 else p


def soften(p: Path, convex: float, concave: float = 0.0) -> Path:
    """Round convex corners by `convex` and fill concave corners by `concave` (plumping)."""
    if concave:
        p = inset(outset(p, concave), concave)
    if convex:
        p = outset(inset(p, convex), convex)
    return p


def sweep(p: Path, dx: float, dy: float, step: float = 1.2) -> Path:
    """Union of `p` translated along (0,0)->(dx,dy): an extrusion silhouette."""
    n = max(2, int(math.ceil(math.hypot(dx, dy) / step)))
    return union(*(move(p, dx * i / n, dy * i / n) for i in range(n + 1)))


def bounds(p: Path):
    return p.bounds


def is_empty(p: Path) -> bool:
    return not list(p.segments) or p.area < 0.01
