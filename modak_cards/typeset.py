"""Modak text as outlines (so the SVGs never depend on an installed font)."""
from __future__ import annotations

from pathlib import Path as FsPath

import pathops
import uharfbuzz as hb
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = FsPath(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "Modak-Regular.ttf"

# Flat tops of Modak's capitals and figures sit ~1300 units up (OS/2 says 1290; overshoots reach 1325).
CAP_UNITS = 1300


class Modak:
    def __init__(self, path: FsPath = FONT_PATH):
        self.tt = TTFont(str(path))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upm = self.tt["head"].unitsPerEm
        self.hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self._outline_cache: dict[str, DecomposingRecordingPen] = {}

    def _outline(self, name: str) -> DecomposingRecordingPen:
        if name not in self._outline_cache:
            rec = DecomposingRecordingPen(self.glyphs)
            self.glyphs[name].draw(rec)
            self._outline_cache[name] = rec
        return self._outline_cache[name]

    def shape(self, text: str, tracking_units: float = 0.0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
        x = 0.0
        out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((self.order[info.codepoint], x + pos.x_offset, pos.y_offset))
            x += pos.x_advance + tracking_units
        return out, x - tracking_units

    def text(self, text: str, cap: float, x: float = 0.0, y: float = 0.0,
             tracking: float = 0.0, anchor: str = "left"):
        """Outline `text` so its capitals are `cap` px tall, baseline at `y`.

        `tracking` is in thousandths of an em. Returns (path, advance_px). Overlapping
        glyphs are unioned, which is what lets tight Modak settings melt together.
        """
        s = cap / CAP_UNITS
        glyphs, adv = self.shape(text, tracking * self.upm / 1000)
        if anchor == "right":
            x -= adv * s
        elif anchor == "center":
            x -= adv * s / 2
        out = pathops.Path()
        for name, gx, gy in glyphs:
            gp = pathops.Path()
            self._outline(name).replay(TransformPen(gp.getPen(), (s, 0, 0, -s, x + gx * s, y - gy * s)))
            out.addPath(gp)
        return pathops.simplify(out), adv * s


_MODAK: Modak | None = None


def modak() -> Modak:
    global _MODAK
    if _MODAK is None:
        _MODAK = Modak()
    return _MODAK
