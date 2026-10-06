"""Build the decks.

    .venv/bin/python -m modak_cards.build                  # both editions + previews
    .venv/bin/python -m modak_cards.build --style 2d       # one edition
    .venv/bin/python -m modak_cards.build --only AS,10H    # a few cards (fast iteration)
    .venv/bin/python -m modak_cards.build --no-preview     # SVG only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .cards import RANKS, build_back, build_card, build_suit_asset, card_ids
from .render import STYLES
from .suits import SUIT_NAMES, SUITS

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "deck"
ASSETS = ROOT / "assets" / "suits"
PREVIEW = ROOT / "previews"


def _split_id(cid: str):
    return cid[:-1], cid[-1]


def _build_one(args):
    style_name, cid = args
    style = STYLES[style_name]
    out = DECK / style_name / f"{cid}.svg"
    svg = build_back(style) if cid == "BACK" else build_card(*_split_id(cid), style)
    out.write_text(svg)
    return str(out)


def _png(svg: Path, png: Path, width: int) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsvg-convert", "-w", str(width), "-o", str(png), str(svg)], check=True)


CARD_W, CARD_H, CARD_R = 750, 1050, 36
SHEET_BG = (43, 43, 43)
SHEET_LABEL = (200, 196, 186)


def _card_image(png: Path, width: int):
    """Card PNG scaled to `width`, with the rounded corners cut out as alpha."""
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGBA")
    h = round(width * CARD_H / CARD_W)
    if im.size != (width, h):
        im = im.resize((width, h), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, width - 1, h - 1], round(CARD_R * width / CARD_W), fill=255)
    im.putalpha(mask)
    return im


def contact_sheet(rows: list[list[tuple[Path, str]]], out: Path, cell_w: int = 188) -> None:
    from PIL import Image, ImageDraw, ImageFont
    cell_h = round(cell_w * CARD_H / CARD_W)
    gap, label_h, margin = 14, 22, 24
    ncols = max(len(r) for r in rows)
    W = margin * 2 + ncols * cell_w + (ncols - 1) * gap
    H = margin * 2 + len(rows) * (cell_h + label_h) + (len(rows) - 1) * gap
    sheet = Image.new("RGB", (W, H), SHEET_BG)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(15)
    for ri, row in enumerate(rows):
        for ci, (png, label) in enumerate(row):
            im = _card_image(png, cell_w)
            x = margin + ci * (cell_w + gap)
            y = margin + ri * (cell_h + label_h + gap)
            sheet.paste(im, (x, y), im)
            tw = draw.textlength(label, font=font)
            draw.text((x + (cell_w - tw) / 2, y + cell_h + 3), label, fill=SHEET_LABEL, font=font)
    sheet.save(out)


def presentation(svgdir: Path, out: Path, hand=("BACK", "AS", "7D", "QH", "10C", "KS")) -> None:
    """A fanned hand of cards on a warm backdrop, for the top of the README."""
    import math
    import tempfile
    from PIL import Image, ImageDraw, ImageFilter
    W, H, card_w = 2400, 1350, 560
    card_h = round(card_w * CARD_H / CARD_W)
    tmp = Path(tempfile.mkdtemp(prefix="modak-hand-"))
    bg = Image.new("RGB", (W, H))
    top, bot = (240, 234, 224), (214, 204, 190)
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bot)))
    radius = card_h * 1.55
    pivot = (W / 2, H * 0.46 + radius)
    step = 9.0
    angles = [(i - (len(hand) - 1) / 2) * step for i in range(len(hand))]
    for cid, ang in zip(hand, angles):
        png = tmp / f"{cid}.png"
        _png(svgdir / f"{cid}.svg", png, card_w)
        card = _card_image(png, card_w)
        rot = card.rotate(-ang, resample=Image.BICUBIC, expand=True)
        a = math.radians(ang)
        cx = pivot[0] + radius * math.sin(a)
        cy = pivot[1] - radius * math.cos(a)
        x, y = round(cx - rot.width / 2), round(cy - rot.height / 2)
        shadow = Image.new("RGBA", rot.size, (40, 30, 20, 0))
        shadow.putalpha(rot.getchannel("A").point(lambda v: v * 0.45))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        bg.paste(shadow, (x + 10, y + 22), shadow)
        bg.paste(rot, (x, y), rot)
        png.unlink()
    tmp.rmdir()
    bg.save(out)


def previews(style_name: str, ids: list[str]) -> None:
    pngdir = PREVIEW / style_name / "png"
    for cid in ids:
        _png(DECK / style_name / f"{cid}.svg", pngdir / f"{cid}.png", 375)
    full = card_ids() + ["BACK"]
    if not all((pngdir / f"{c}.png").exists() for c in full):
        return
    rows = [[(pngdir / f"{c}{s}.png", f"{c}{s}") for c in RANKS] for s in SUITS]
    rows.append([(pngdir / "BACK.png", "BACK")])
    contact_sheet(rows, PREVIEW / f"contact-{style_name}.png")
    presentation(DECK / style_name, PREVIEW / f"presentation-{style_name}.png")


def compare() -> None:
    pairs = ["7S", "KH", "AD", "3C"]
    row = []
    for cid in pairs:
        for st in ("3d", "2d"):
            p = PREVIEW / st / "png" / f"{cid}.png"
            if not p.exists():
                return
            row.append((p, f"{cid} {st.upper()}"))
    contact_sheet([row], PREVIEW / "compare-3d-vs-2d.png", cell_w=280)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--style", choices=["3d", "2d", "all"], default="all")
    ap.add_argument("--only", help="comma-separated card ids, e.g. AS,10H,BACK")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--jobs", type=int, default=None)
    a = ap.parse_args(argv)

    styles = ["3d", "2d"] if a.style == "all" else [a.style]
    ids = a.only.split(",") if a.only else card_ids() + ["BACK"]
    for st in styles:
        (DECK / st).mkdir(parents=True, exist_ok=True)
    work = [(st, cid) for st in styles for cid in ids]
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for path in pool.map(_build_one, work):
            print("wrote", Path(path).relative_to(ROOT))

    if not a.only:
        for st in styles:
            out = ASSETS / st
            out.mkdir(parents=True, exist_ok=True)
            for code in SUITS:
                f = out / f"{SUIT_NAMES[code].lower()[:-1]}.svg"
                f.write_text(build_suit_asset(code, STYLES[st]))
                print("wrote", f.relative_to(ROOT))

    if not a.no_preview:
        for st in styles:
            previews(st, ids)
        compare()
    return 0


if __name__ == "__main__":
    sys.exit(main())
