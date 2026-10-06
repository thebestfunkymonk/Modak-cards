"""SVG output and the two finishes.

`Puffy3D` fakes Hiero's soft clay relief with plain vector parts only (no SVG filters, so
files open the same in browsers, Illustrator, Figma and Inkscape): a contact shadow made of
stacked translucent strokes, an extrusion silhouette, a gradient face, and translucent
bevel strips cut from the face with boolean ops. `Flat2D` is the same artwork as solid
fills. Both share the Hiero wireframe (solid-vs-outline) and seam treatments.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from pathops import Path

from .geom import d, diff, inter, is_empty, move, poly, stroke_outline, sweep, union

PAPER = "#FFF7EC"

PALETTES = {
    "ink": dict(base="#2C2634", top="#4E4559", side="#18131D", side2="#0D0A11", shade="#000000",
                light="#FFFFFF", tint="#8C8494"),
    "red": dict(base="#E8402F", top="#FF7A61", side="#A8291D", side2="#78190F", shade="#4A0700",
                light="#FFFFFF", tint="#F29C90"),
    "paper": dict(base=PAPER, top="#FFFFFF", side="#E5B5A3", side2="#C48876", shade="#7A2416",
                  light="#FFFFFF", tint="#F7C3B8"),
}
SHADOW_ON = {"paper": "#4A3426", "red": "#5C0B04", "ink": "#000000"}


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def el(p: Path, fill: str, opacity: float | None = None, extra: str = "") -> str:
    if is_empty(p):
        return ""
    op = f' opacity="{opacity:.3f}"' if opacity is not None and opacity < 1 else ""
    return f'<path d="{d(p)}" fill="{fill}"{op}{extra}/>'


@dataclass
class Svg:
    w: float
    h: float
    title: str = ""
    defs: dict = field(default_factory=dict)
    body: list = field(default_factory=list)

    def gradient(self, gid: str, top: str, bottom: str, x2: float = 0, y2: float = 1) -> str:
        if gid not in self.defs:
            self.defs[gid] = (
                f'<linearGradient id="{gid}" x1="0" y1="0" x2="{fmt(x2)}" y2="{fmt(y2)}">'
                f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
                f"</linearGradient>"
            )
        return f"url(#{gid})"

    def add(self, *parts: str):
        self.body.extend(p for p in parts if p)

    def group(self, gid: str, parts, transform: str = "") -> str:
        inner = "".join(p for p in parts if p)
        if not inner:
            return ""
        t = f' transform="{transform}"' if transform else ""
        return f'<g id="{gid}"{t}>{inner}</g>'

    def tostring(self) -> str:
        title = f"<title>{self.title}</title>" if self.title else ""
        defs = f"<defs>{''.join(self.defs.values())}</defs>" if self.defs else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(self.w)}" height="{fmt(self.h)}" '
            f'viewBox="0 0 {fmt(self.w)} {fmt(self.h)}">{title}{defs}{"".join(self.body)}</svg>\n'
        )


def seam_strip(seg, width: float, shift: float = 0.0) -> Path:
    (ax, ay), (bx, by) = seg
    L = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / L, (bx - ax) / L
    o1, o2 = shift - width / 2, shift + width / 2
    return poly([(ax + nx * o1, ay + ny * o1), (bx + nx * o1, by + ny * o1),
                 (bx + nx * o2, by + ny * o2), (ax + nx * o2, ay + ny * o2)])


def wire(p: Path, width: float) -> Path:
    """Hiero's hairline 'wireframe' state of a shape, as a filled outline."""
    return stroke_outline(p, width)


class Flat2D:
    name = "2d"
    label = "2D"

    def paper(self, svg: Svg, card: Path) -> str:
        return el(card, PAPER)

    def band(self, svg: Svg, band: Path, color: str) -> str:
        return el(band, PALETTES[color]["base"])

    def solid(self, svg: Svg, p: Path, color: str, size: float, seams=(), on: str = "paper",
              **_) -> str:
        pal = PALETTES[color]
        parts = [el(p, pal["base"])]
        sw = max(1.4, 0.022 * size)
        for seg in seams:
            parts.append(el(inter(seam_strip(seg, sw), p), PALETTES[on]["base"]))
        return "".join(parts)

    def small(self, svg: Svg, p: Path, color: str, size: float, seams=(), on: str = "paper") -> str:
        return self.solid(svg, p, color, size, seams, on)


class Puffy3D(Flat2D):
    name = "3d"
    label = "3D"

    def paper(self, svg: Svg, card: Path) -> str:
        return el(card, svg.gradient("paper-grad", "#FFFAF2", "#FBEEDD"))

    def band(self, svg: Svg, band: Path, color: str) -> str:
        pal = PALETTES[color]
        x0, y0, x1, y1 = band.bounds
        lip = inter(band, poly([(x0, y0), (x1, y0), (x1, y0 + 3), (x0, y0 + 3)]))
        return el(band, svg.gradient(f"band-{color}", pal["top"], pal["base"], 0, 0.35)) + el(
            lip, pal["light"], 0.35)

    def solid(self, svg: Svg, p: Path, color: str, size: float, seams=(), on: str = "paper",
              depth: float | None = None, shadow: bool = True) -> str:
        pal = PALETTES[color]
        depth = depth if depth is not None else max(1.6, 0.024 * size)
        ex, ey = 0.3 * depth, depth
        parts = []

        if shadow:
            sh = d(move(p, ex * 1.4, ey * 1.9))
            col = SHADOW_ON[on]
            for i, w in enumerate((0.0, 0.035 * size, 0.07 * size, 0.11 * size)):
                stroke = (f' stroke="{col}" stroke-width="{fmt(w)}" stroke-linejoin="round"' if w else "")
                parts.append(f'<path d="{sh}" fill="{col}"{stroke} opacity="{fmt(0.05 if i else 0.07)}"/>')

        body = sweep(p, ex, ey, step=max(0.5, depth / 14))
        side = diff(body, p)
        parts.append(el(side, svg.gradient(f"side-{color}", pal["side"], pal["side2"])))
        parts.append(el(p, svg.gradient(f"face-{color}", pal["top"], pal["base"])))

        # Many thin, faint strips (about 1.5 px apart) blend into a smooth pillow edge;
        # a few wide ones show up as terraces.
        bevel = 0.05 * size
        steps = max(3, min(22, round(bevel / 1.4)))
        hl_a = 1 - (1 - 0.38) ** (1 / steps)
        sh_a = 1 - (1 - 0.42) ** (1 / steps)
        for i in range(1, steps + 1):
            a = bevel * (i / steps) ** 1.5
            parts.append(el(diff(p, move(p, 0.35 * a, a)), pal["light"], hl_a))
            parts.append(el(diff(p, move(p, -0.35 * a, -a)), pal["shade"], sh_a))
        rim = max(0.9, 0.009 * size)
        parts.append(el(diff(p, move(p, 0.3 * rim, rim)), pal["light"], 0.6))

        sw = max(1.2, 0.018 * size)
        for seg in seams:
            parts.append(el(inter(seam_strip(seg, sw), union(p, side)), pal["side2"], 0.85))
            parts.append(el(inter(seam_strip(seg, sw * 0.8, sw * 0.95), p), pal["light"], 0.35))
        return "".join(parts)

    def small(self, svg: Svg, p: Path, color: str, size: float, seams=(), on: str = "paper") -> str:
        """Index-sized marks: a shallow version that stays crisp at 70 px."""
        pal = PALETTES[color]
        depth = max(1.4, 0.03 * size)
        side = diff(sweep(p, 0.3 * depth, depth, step=0.5), p)
        parts = [el(side, svg.gradient(f"side-{color}", pal["side"], pal["side2"])),
                 el(p, svg.gradient(f"face-{color}", pal["top"], pal["base"]))]
        rim = max(0.8, 0.02 * size)
        parts.append(el(diff(p, move(p, 0.3 * rim, rim)), pal["light"], 0.45))
        sw = max(1.2, 0.022 * size)
        for seg in seams:
            parts.append(el(inter(seam_strip(seg, sw), p), pal["side2"], 0.8))
        return "".join(parts)


STYLES = {"3d": Puffy3D(), "2d": Flat2D()}
