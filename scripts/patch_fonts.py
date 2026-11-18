"""Patch missing ASCII/punctuation glyphs into Vita Font24.fnt and Font30.fnt."""

from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

BACKUP_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\backup\PCSG00841")
VITA_DIR = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841")
TTF_PATH = Path(r"C:\Windows\Fonts\arialbd.ttf")

# Printable ASCII 0x20..0x7E plus common typographic punctuation + half-width space marker (｡ = 0xA1 SJIS -> 0xEFBDA1 UTF-8)
TARGET_CHARS = [chr(c) for c in range(0x20, 0x7F)] + ["’", "‘", "“", "”", "—", "–", "…", "｡"]


def utf8_code_int(ch: str) -> int:
    """Pack UTF-8 bytes big-endian into a uint32 matching Sting .fnt format."""
    b = ch.encode("utf-8")
    return int.from_bytes(b, "big")


def build_alpha_lut(pal_bytes: bytes) -> list[int]:
    """Map 0..255 alpha to nearest palette index with (255,255,255,A) or (0,0,0,0)."""
    entries = []
    for idx in range(256):
        r, g, b, a = pal_bytes[idx * 4 : idx * 4 + 4]
        if idx == 0 or (r == 255 and g == 255 and b == 255):
            entries.append((idx, a))
    lut = []
    for alpha in range(256):
        best_idx = min(entries, key=lambda ia: abs(ia[1] - alpha))[0]
        lut.append(best_idx)
    return lut


def is_cjk_kanji(code: int) -> bool:
    """True for 3-byte UTF-8 CJK Unified Ideographs (0xE4B880..0xE9BEBF)."""
    return 0xE4B880 <= code <= 0xE9BEBF


def render_glyph(ch: str, cell_sz: int, font: ImageFont.FreeTypeFont, baseline_y: int) -> Image.Image:
    """Render a single character horizontally centered at baseline_y inside a cell_sz x cell_sz image."""
    img = Image.new("L", (cell_sz, cell_sz), 0)
    if ch in (" ", "｡"):
        return img
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=font, anchor="ls")
    gw = bbox[2] - bbox[0]
    x = max(0, (cell_sz - gw) // 2 - bbox[0])
    draw.text((x, baseline_y), ch, fill=255, font=font, anchor="ls")
    return img


def patch_font(src_path: Path, dst_path: Path, cell_sz: int, ttf_size: int, baseline_y: int) -> None:
    data = bytearray(src_path.read_bytes())
    tbl_sz, font_px, num_glyphs = struct.unpack_from("<III", data, 20)
    tex_hdr_off = tbl_sz + 20
    _tex_sz, _flags, _data_sz, tex_w, tex_h = struct.unpack_from("<5I", data, tex_hdr_off)
    pix_start = tex_hdr_off + 20
    pal_start = pix_start + tex_w * tex_h

    alpha_lut = build_alpha_lut(bytes(data[pal_start : pal_start + 1024]))
    ttf = ImageFont.truetype(str(TTF_PATH), ttf_size)

    existing_codes = {}
    kanji_slots = []
    for i in range(num_glyphs):
        code, u, v = struct.unpack_from("<Iff", data, 32 + i * 12)
        existing_codes[code] = i
        if i > 0 and is_cjk_kanji(code):
            kanji_slots.append(i)

    missing = [ch for ch in TARGET_CHARS if utf8_code_int(ch) not in existing_codes]
    already = [ch for ch in TARGET_CHARS if utf8_code_int(ch) in existing_codes]
    if len(missing) > len(kanji_slots):
        raise RuntimeError(f"{src_path.name}: need {len(missing)} slots, only {len(kanji_slots)} CJK slots")

    def write_glyph_to_slot(ch: str, slot: int, new_code: int | None = None) -> None:
        _old_code, u, v = struct.unpack_from("<Iff", data, 32 + slot * 12)
        x0 = round(u * tex_w)
        y0 = round(v * tex_h)
        glyph_img = render_glyph(ch, cell_sz, ttf, baseline_y)
        px = glyph_img.load()
        for dy in range(cell_sz):
            row_off = pix_start + (y0 + dy) * tex_w + x0
            for dx in range(cell_sz):
                data[row_off + dx] = alpha_lut[px[dx, dy]]
        if new_code is not None:
            struct.pack_into("<I", data, 32 + slot * 12, new_code)

    # Re-render existing ASCII glyphs so they match the uniform bold style (no skinny UI glyphs)
    for ch in already:
        if ch == " ":
            continue
        write_glyph_to_slot(ch, existing_codes[utf8_code_int(ch)])

    # Replace kanji slots from the end backwards, avoiding the very last slot
    slots_to_use = [s for s in reversed(kanji_slots) if s < num_glyphs - 1]
    for ch, slot in zip(missing, slots_to_use):
        write_glyph_to_slot(ch, slot, utf8_code_int(ch))

    # Sort glyph table ascending by UTF-8 code so binary search never misses A/B/x
    entries = [struct.unpack_from("<Iff", data, 32 + i * 12) for i in range(num_glyphs)]
    entries.sort(key=lambda e: e[0])
    for i, (c, u, v) in enumerate(entries):
        struct.pack_into("<Iff", data, 32 + i * 12, c, u, v)

    dst_path.write_bytes(data)
    print(f"Patched {dst_path.name}: added {len(missing)} glyphs ({missing[:10]}...)")


def main() -> None:
    patch_font(BACKUP_DIR / "Font24.fnt", VITA_DIR / "Font24.fnt", cell_sz=28, ttf_size=18, baseline_y=21)
    patch_font(BACKUP_DIR / "Font30.fnt", VITA_DIR / "Font30.fnt", cell_sz=34, ttf_size=23, baseline_y=25)


if __name__ == "__main__":
    main()
