"""Card layouts: the Helveticards grid, dressed in Modak and Hiero."""
from __future__ import annotations

from pathops import Path

from .geom import d, diff, inter, is_empty, move, outset, rect, rotate180, rrect, union
from .render import PALETTES, Svg, el, seam_strip, wire
from .suits import SUIT_COLOR, SUIT_NAMES, crown, suit, suit_width_ratio
from .typeset import modak

W, H, RADIUS = 750.0, 1050.0, 36.0  # 2.5 x 3.5 in at 300 ppi
M = 52.0
INDEX_CAP, INDEX_BASE = 66.0, 52.0 + 66.0
NAME_CAP = 27.0
PIP_H, PIP_GAP, PIP_COLS, PIP_Y0 = 62.0, 20.0, 3, 172.0
BAND_TOP = 800.0
NUM_CAP, NUM_BASE, NUM_BLEED = 610.0, 905.0, 0.06
WIRE_W = 5.0

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
RANK_WORDS = {"A": "Ace", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six",
              "7": "Seven", "8": "Eight", "9": "Nine", "10": "Ten", "J": "Jack", "Q": "Queen",
              "K": "King"}
# Modak's "1" and "0" are set tight enough to melt into one body.
NUM_TRACKING = {"10": -70.0}
INDEX_TRACKING = {"10": -60.0}


def card_ids():
    return [f"{r}{s}" for s in ("S", "H", "D", "C") for r in RANKS]


def _clip(svg: Svg, card: Path) -> None:
    svg.defs["clip"] = f'<clipPath id="card-clip"><path d="{d(card)}"/></clipPath>'


def _name_line(rank: str, suit_code: str):
    """'Five of Clubs', right-aligned. Returns [(path, is_tint)]."""
    f = modak()
    words = [(RANK_WORDS[rank], False), ("of", True), (SUIT_NAMES[suit_code], False)]
    space = f.text(" ", NAME_CAP)[1] * 0.85
    widths = [f.text(w, NAME_CAP)[1] for w, _ in words]
    x = W - M - (sum(widths) + space * (len(words) - 1))
    base = INDEX_BASE - (INDEX_CAP - NAME_CAP) / 2
    out = []
    for (word, tint), wdt in zip(words, widths):
        out.append((f.text(word, NAME_CAP, x, base)[0], tint))
        x += wdt + space
    return out


def _index(rank: str, suit_code: str):
    rank_p, rank_w = modak().text(rank, INDEX_CAP, M, INDEX_BASE, tracking=INDEX_TRACKING.get(rank, 0))
    rx1 = rank_p.bounds[2]
    pip_h = INDEX_CAP * 0.8
    pip_w = pip_h * suit_width_ratio(suit_code)
    sp, seams, _ = suit(suit_code, rx1 + 10 + pip_w / 2, INDEX_BASE - INDEX_CAP / 2, pip_h)
    return rank_p, (sp, seams, pip_h)


def _pip_positions(n: int):
    pitch = PIP_H + PIP_GAP
    xs = [M + PIP_H * 0.55 + c * pitch for c in range(PIP_COLS)]
    return [(xs[i % PIP_COLS], PIP_Y0 + PIP_H / 2 + (i // PIP_COLS) * pitch) for i in range(n)]


def _place_numeral(text: str, keepouts) -> tuple[Path, float]:
    cap = NUM_CAP
    while True:
        p, _ = modak().text(text, cap, 0, NUM_BASE, tracking=NUM_TRACKING.get(text, 0))
        x0, _, x1, _ = p.bounds
        p = move(p, W + NUM_BLEED * (x1 - x0) - x1, 0)
        if cap < 320 or all(is_empty(inter(p, k)) for k in keepouts):
            return p, cap
        cap *= 0.98


def _split_wire(svg, style, p: Path, seams, color: str, size: float) -> str:
    """Hiero's signature: one half of the mark solid, the other half left as wireframe."""
    (ax, _), _ = seams[0]
    x0, y0, x1, y1 = p.bounds
    left = inter(p, rect(x0 - 50, y0 - 50, ax - x0 + 50, y1 - y0 + 100))
    right = inter(p, rect(ax, y0 - 50, x1 - ax + 50, y1 - y0 + 100))
    rest = [sg for sg in seams[1:]]
    wire_w = max(WIRE_W * 0.9, size * 0.016)
    return el(wire(right, wire_w), PALETTES[color]["base"]) + style.solid(svg, left, color, size, rest)


def build_card(rank: str, suit_code: str, style) -> str:
    color = SUIT_COLOR[suit_code]
    pal = PALETTES[color]
    title = f"{RANK_WORDS[rank]} of {SUIT_NAMES[suit_code]}"
    svg = Svg(W, H, f"{title} | Modak cards {style.label}")
    card = rrect(0, 0, W, H, RADIUS)
    _clip(svg, card)
    band = inter(card, rect(0, BAND_TOP, W, H - BAND_TOP))

    rank_p, (ipip, iseams, ipip_h) = _index(rank, suit_code)
    names = _name_line(rank, suit_code)
    keepouts = [outset(union(rank_p, ipip, *(p for p, _ in names)), 34)]

    art = []
    if rank == "A":
        big_h = 300.0 if suit_code == "S" else 270.0
        bw = big_h * suit_width_ratio(suit_code)
        p, seams, _ = suit(suit_code, M + bw / 2, PIP_Y0 + big_h / 2, big_h)
        art.append(_split_wire(svg, style, p, seams, color, big_h))
        keepouts.append(outset(p, 40))
    elif rank in ("J", "Q", "K"):
        sh = 190.0
        sw = sh * suit_width_ratio(suit_code)
        cx = M + sw / 2
        crown_p = crown(rank, cx, PIP_Y0 + 58, sw * 0.82)
        p, seams, _ = suit(suit_code, cx, PIP_Y0 + 80 + sh / 2, sh)
        art.append(el(wire(crown_p, WIRE_W * 0.9), pal["base"]))
        art.append(style.solid(svg, p, color, sh, seams))
        keepouts.append(outset(union(p, crown_p), 40))
    else:
        pips = []
        for x, y in _pip_positions(int(rank)):
            p, seams, _ = suit(suit_code, x, y, PIP_H)
            art.append(style.solid(svg, p, color, PIP_H, seams))
            pips.append(p)
        keepouts.append(outset(union(*pips), 44))

    cx, cy = W / 2, H / 2
    numeral, num_cap = _place_numeral(rank, keepouts)
    numeral_solid = style.solid(svg, numeral, color, num_cap)
    inverted_index = outset(rotate180(union(rank_p, ipip), cx, cy), 16)
    numeral_wire = el(diff(inter(wire(numeral, WIRE_W), band), inverted_index), PALETTES["paper"]["base"])

    top_row = [style.small(svg, rank_p, color, INDEX_CAP), style.small(svg, ipip, color, ipip_h, iseams)]
    for p, tint in names:
        top_row.append(el(p, pal["tint"] if tint else pal["base"]))

    flat = []
    for p, seams in ((rank_p, ()), (ipip, iseams)):
        rp = rotate180(p, cx, cy)
        flat.append(el(rp, PALETTES["paper"]["base"]))
        for seg in seams:
            (ax, ay), (bx, by) = seg
            rseg = ((2 * cx - ax, 2 * cy - ay), (2 * cx - bx, 2 * cy - by))
            flat.append(el(inter(seam_strip(rseg, max(1.4, 0.022 * ipip_h)), rp), pal["base"]))
    for p, tint in names:
        flat.append(el(rotate180(p, cx, cy), PALETTES["paper"]["base"], 0.6 if tint else None))

    svg.add(
        f'<g clip-path="url(#card-clip)">',
        svg.group("paper", [style.paper(svg, card)]),
        svg.group("art", art),
        svg.group("numeral", [numeral_solid]),
        svg.group("band", [style.band(svg, band, color)]),
        svg.group("numeral-wire", [numeral_wire]),
        svg.group("index", top_row),
        svg.group("index-inverted", flat),
        "</g>",
    )
    return svg.tostring()


def build_back(style) -> str:
    svg = Svg(W, H, f"Card back | Modak cards {style.label}")
    card = rrect(0, 0, W, H, RADIUS)
    _clip(svg, card)
    red = PALETTES["red"]
    field = (el(card, svg.gradient("back-field", red["top"], red["base"], 0.0, 0.6))
             if style.name == "3d" else el(card, red["base"]))

    # Two Hiero 3x7 bars crossed into a plus (a nod to Helveticards' Swiss cross): the
    # upright is solid, the crossbar is left as wireframe behind it. Symmetric under 180°.
    long_side = 350.0
    short_side = long_side * 3 / 7
    cx, cy = W / 2, H / 2
    bar_h = rrect(cx - long_side / 2, cy - short_side / 2, long_side, short_side, 20)
    bar_v = rrect(cx - short_side / 2, cy - long_side / 2, short_side, long_side, 20)
    crossbar = diff(wire(bar_h, WIRE_W * 1.2), outset(bar_v, WIRE_W * 2.5))
    plus_art = (el(crossbar, PALETTES["paper"]["base"])
                + style.solid(svg, bar_v, "paper", long_side * 0.6, on="red"))

    f = modak()
    cap = 50.0
    modak_p, modak_w = f.text("Modak", cap, M + 6, M + 18 + cap)
    cards_p, _ = f.text("cards", cap, M + 6 + modak_w + 2, M + 18 + cap)
    marks = []
    for p, tint in ((modak_p, False), (cards_p, True)):
        for q in (p, rotate180(p, cx, cy)):
            marks.append(el(q, PALETTES["paper"]["base"], 0.62 if tint else None))

    svg.add(
        f'<g clip-path="url(#card-clip)">',
        svg.group("field", [field]),
        svg.group("plus", [plus_art]),
        svg.group("wordmark", marks),
        "</g>",
    )
    return svg.tostring()


def build_suit_asset(suit_code: str, style, size: float = 512.0) -> str:
    color = SUIT_COLOR[suit_code]
    svg = Svg(size, size, f"{SUIT_NAMES[suit_code]} | Modak cards {style.label}")
    h = size * 0.7
    p, seams, _ = suit(suit_code, size / 2, size / 2 - size * 0.02, h)
    svg.add(svg.group("suit", [style.solid(svg, p, color, h, seams)]))
    return svg.tostring()
