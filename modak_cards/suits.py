"""Suit symbols and court crowns.

Every mark is assembled the Hiero way, from circles, 3x7 rectangles and isosceles right
triangles only, then "plumped" Modak-style: concave joints are filled and convex
corners rounded, so the pieces read as one soft, bubbly body. The assembly joints
survive as seams.
"""
from __future__ import annotations

import math
from functools import lru_cache

from pathops import Path

from .geom import affine, circle, inter, poly, rect, rrect, soften, union

S2 = math.sqrt(2)
SUITS = ("S", "H", "D", "C")
SUIT_NAMES = {"S": "Spades", "H": "Hearts", "D": "Diamonds", "C": "Clubs"}
SUIT_COLOR = {"S": "ink", "C": "ink", "H": "red", "D": "red"}

# Seams are segments in the same design space as the shape (long enough to cross it).
V_SEAM = ((0.0, -400.0), (0.0, 400.0))
H_SEAM = ((-400.0, 0.0), (400.0, 0.0))


def _heart_body() -> Path:
    """Rotated square (two isosceles right triangles) plus two circles on its upper edges."""
    a = 100.0
    h = a / S2
    square = poly([(0, -h), (h, 0), (0, h), (-h, 0)])
    r = 0.54 * a
    push = 0.03 * a / S2
    lobes = [circle(sx * (h / 2 + push), -h / 2 - push, r) for sx in (-1, 1)]
    return union(square, *lobes)


def _triangle_apex_up(apex_y: float, height: float) -> Path:
    """Isosceles right triangle, right angle at the apex, hypotenuse horizontal below."""
    return poly([(0, apex_y), (height, apex_y + height), (-height, apex_y + height)])


@lru_cache(maxsize=None)
def _raw(suit: str):
    if suit == "H":
        return soften(_heart_body(), convex=7, concave=10), (V_SEAM,), 0.0
    if suit == "S":
        body = affine(_heart_body(), 1, 0, 0, -1, 0, 0)
        stem = _triangle_apex_up(66, 50)
        return soften(union(body, stem), convex=6, concave=11), (V_SEAM,), 0.0
    if suit == "C":
        r = 31.0
        lobes = [circle(0, -34, r), circle(-38, 16, r), circle(38, 16, r), circle(0, 10, 25)]
        stem = _triangle_apex_up(38, 46)
        return soften(union(*lobes, stem), convex=5, concave=9), (V_SEAM,), 0.0
    if suit == "D":
        w, hgt = 54.0, 64.0
        body = poly([(0, -hgt), (w, 0), (0, hgt), (-w, 0)])
        return soften(body, convex=9), (V_SEAM, H_SEAM), 0.0
    raise KeyError(suit)


# Pointed shapes look small next to round ones; nudge them so all four sit the same size.
OPTICAL = {"S": 1.02, "H": 0.97, "D": 1.06, "C": 1.0}


def _fit(path: Path, seams, cx: float, cy: float, h: float, optical: float = 1.0):
    x0, y0, x1, y1 = path.bounds
    s = h * optical / (y1 - y0)
    bx, by = (x0 + x1) / 2, (y0 + y1) / 2
    tx, ty = cx - s * bx, cy - s * by
    placed = affine(path, s, 0, 0, s, tx, ty)
    placed_seams = [((s * ax + tx, s * ay + ty), (s * bx2 + tx, s * by2 + ty)) for (ax, ay), (bx2, by2) in seams]
    return placed, placed_seams, s


def suit(code: str, cx: float, cy: float, h: float):
    """Suit `code` centred on (cx, cy), `h` px tall. Returns (path, seams, width)."""
    path, seams, _ = _raw(code)
    placed, placed_seams, _ = _fit(path, seams, cx, cy, h, OPTICAL[code])
    x0, _, x1, _ = placed.bounds
    return placed, placed_seams, x1 - x0


def suit_width_ratio(code: str) -> float:
    path, _, _ = _raw(code)
    x0, y0, x1, y1 = path.bounds
    return (x1 - x0) / ((y1 - y0) * OPTICAL[code])


@lru_cache(maxsize=None)
def _crown_raw(rank: str) -> Path:
    """Court headwear on a 3x7 band: K spikes, Q pearls, J a domed cap."""
    band = rrect(-50, 0, 100, 100 * 3 / 7 * 0.5, 4)
    if rank == "K":
        w = 100 / 3
        teeth = [poly([(x, 0.5), (x + w, 0.5), (x + w / 2, -w / 2)]) for x in (-50, -50 + w, -50 + 2 * w)]
        return soften(union(band, *teeth), convex=2.5, concave=3)
    if rank == "Q":
        pearls = [circle(x, -13, 13) for x in (-34, 0, 34)]
        return soften(union(band, *pearls), convex=2, concave=4)
    if rank == "J":
        dome = inter(circle(0, 2, 40), rect(-40, -40, 80, 42))
        return soften(union(band, dome), convex=2, concave=4)
    raise KeyError(rank)


def crown(rank: str, cx: float, bottom: float, w: float) -> Path:
    path = _crown_raw(rank)
    x0, y0, x1, y1 = path.bounds
    s = w / (x1 - x0)
    return affine(path, s, 0, 0, s, cx - s * (x0 + x1) / 2, bottom - s * y1)
