"""Port PC EN textures (Character.pck nameplates, Dungeon/st*/UI.tex & Data.pck[0], and main UI.tex) to Vita PCSG00841."""
from pathlib import Path
import io
import shutil
import struct
from PIL import Image

PC_DATA_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\DungeonTravelers2-2_EN\Data\ENG")
VITA_APP_DIR = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841")
BACKUP_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\backup\PCSG00841")


def read_pck_entries(b: bytes) -> tuple[int, int, list[bytes]]:
    p_off = b.find(b"Pack                ")
    cnt = struct.unpack_from("<I", b, p_off + 24)[0]
    entries = []
    for i in range(cnt):
        off, sz = struct.unpack_from("<II", b, p_off + 28 + i * 8)
        entries.append(b[off : off + sz])
    return p_off, cnt, entries


def build_pck_from_template(template_b: bytes, new_entries: list[bytes]) -> bytes:
    p_off = template_b.find(b"Pack                ")
    cnt = struct.unpack_from("<I", template_b, p_off + 24)[0]
    if len(new_entries) != cnt:
        raise ValueError(f"Expected {cnt} entries, got {len(new_entries)}")
    first_off = struct.unpack_from("<I", template_b, p_off + 28)[0]
    out = bytearray(template_b[:first_off])

    meta = []
    for entry in new_entries:
        no = len(out)
        out.extend(entry)
        pad = (-len(out)) % 16
        if pad:
            out.extend(b"\x00" * pad)
        meta.append((no, len(entry)))

    for i, (no, ns) in enumerate(meta):
        struct.pack_into("<II", out, p_off + 28 + i * 8, no, ns)
    return bytes(out)


def decompress_lz77(lz: bytes) -> bytes:
    magic, out_sz, token_cnt, data_off = struct.unpack_from("<4I", lz, 0)
    if lz[:4] != b"LZ77":
        raise ValueError(f"Expected LZ77 magic, got {lz[:4]!r}")
    out = bytearray(out_sz)
    dst = 0
    flag_pos = 16
    data_pos = data_off
    flags = 0
    bits = 0
    for _ in range(token_cnt):
        if bits == 0:
            flags = lz[flag_pos]
            flag_pos += 1
            bits = 8
        if flags & 0x80:
            dist = lz[data_pos]
            count = lz[data_pos + 1] + 3
            data_pos += 2
            src = dst - dist
            for _ in range(count):
                out[dst] = out[src]
                dst += 1
                src += 1
        else:
            out[dst] = lz[data_pos]
            dst += 1
            data_pos += 1
        flags = (flags & 0x7F) << 1
        bits -= 1
    return bytes(out)


def decode_pc_tex(b: bytes) -> tuple[Image.Image, list[tuple[float, ...]], bytes]:
    t_off = b.find(b"Texture             ")
    chunk_sz, unk, flags, data_sz, pw, ph = struct.unpack_from("<4IHH", b, t_off + 20)
    raw = decompress_lz77(b[t_off + 40 : t_off + 40 + data_sz])
    img = Image.frombytes("RGBA", (pw, ph), raw)
    p_off = b.find(b"Parts               ")
    p_sz, p_cnt = struct.unpack_from("<II", b, p_off + 20)
    parts = [struct.unpack_from("<8f", b, p_off + 28 + i * 32) for i in range(p_cnt)]
    a_off = b.find(b"Anime               ")
    return img, parts, b[a_off:]


def build_vita_tex(
    png_bytes: bytes,
    w: int,
    h: int,
    parts: list[tuple[float, ...]],
    anime_tail: bytes,
    flags: int = 0x81014000,
) -> bytes:
    out = bytearray()
    # 1. Texture chunk (aligned to 8 bytes from start of chunk)
    t_data_sz = len(png_bytes)
    t_chunk_sz = 20 + 20 + t_data_sz
    out.extend(b"Texture             ")
    out.extend(struct.pack("<5I", t_chunk_sz, flags, t_data_sz, w, h))
    out.extend(png_bytes)
    pad = (-len(out)) % 8
    if pad:
        out.extend(b"\x00" * pad)

    # 2. Parts chunk
    p_cnt = len(parts)
    p_chunk_sz = 20 + 8 + p_cnt * 32
    out.extend(b"Parts               ")
    out.extend(struct.pack("<II", p_chunk_sz, p_cnt))
    for pt in parts:
        out.extend(struct.pack("<8f", *pt))
    pad = (-len(out)) % 8
    if pad:
        out.extend(b"\x00" * pad)

    # 3. Anime chunk + trailing terminator
    out.extend(anime_tail)
    return bytes(out)


def convert_single_sheet_pc_to_vita(v_tex: bytes, p_tex: bytes, zero_origins: set[int] | None = None) -> bytes:
    """Downscale PC LZ77 texture by 0.5x to Vita linear PNG (flags=0x81014000) with 8-pixel aligned width."""
    p_img, p_parts, _ = decode_pc_tex(p_tex)
    a_off = v_tex.find(b"Anime               ")
    v_anime_tail = v_tex[a_off:]

    pw, ph = p_img.size
    raw_vw = max(1, (pw + 1) // 2)
    raw_vh = max(1, (ph + 1) // 2)
    # Vita GXM requires texture width to be a multiple of 8 pixels (32-byte stride at 0x81241A74)
    vw = (raw_vw + 7) & ~7
    vh = raw_vh

    scaled_img = p_img.resize((raw_vw, raw_vh), Image.Resampling.LANCZOS)
    if vw == raw_vw:
        v_img = scaled_img
    else:
        v_img = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        v_img.paste(scaled_img, (0, 0))

    buf = io.BytesIO()
    v_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    new_parts = []
    for idx, (px, py, ppw, pph, pu0, pv0, pu1, pv1) in enumerate(p_parts):
        if zero_origins and idx in zero_origins:
            nx, ny = 0.0, 0.0
        else:
            nx, ny = round(px * 0.5, 2), round(py * 0.5, 2)
        nw = round(ppw * 0.5, 2)
        nh = round(pph * 0.5, 2)
        # Recompute horizontal UVs for padded canvas width vw
        nu0 = (pu0 * raw_vw) / float(vw)
        nu1 = (pu1 * raw_vw) / float(vw)
        new_parts.append((nx, ny, nw, nh, nu0, pv0, nu1, pv1))

    return build_vita_tex(png_bytes, vw, vh, new_parts, v_anime_tail, flags=0x81014000)


def patch_character_pck() -> None:
    rel = Path("Character/Character.pck")
    vp = VITA_APP_DIR / rel
    pp = PC_DATA_DIR / rel
    bak = BACKUP_DIR / rel
    if not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vp, bak)

    vb = bak.read_bytes()
    pb = pp.read_bytes()
    _, vc, v_chars = read_pck_entries(vb)
    _, pc, p_chars = read_pck_entries(pb)

    new_chars = []
    for i, (v_sub_pck, p_sub_pck) in enumerate(zip(v_chars, p_chars)):
        _, _, v_subs = read_pck_entries(v_sub_pck)
        _, _, p_subs = read_pck_entries(p_sub_pck)
        # Keep Part[0..2] origin (x=0, y=0) as on Vita so dialogue ribbon and inline CStringBase drawing don't shift
        ported_ui_tex = convert_single_sheet_pc_to_vita(v_subs[-1], p_subs[-1], zero_origins={0, 1, 2})
        merged_subs = p_subs[:-1] + [ported_ui_tex]
        new_chars.append(build_pck_from_template(v_sub_pck, merged_subs))

    vp.write_bytes(build_pck_from_template(vb, new_chars))
    print(f"Patched Character/Character.pck ({vc} characters: PlayerData.txt + chatter barks + English nameplate UI.tex)")


def patch_dungeon_textures() -> None:
    # 1. All Dungeon/st*/UI.tex
    ui_cnt = 0
    for v_ui_path in sorted((VITA_APP_DIR / "Dungeon").glob("st*/UI.tex")):
        rel = v_ui_path.relative_to(VITA_APP_DIR)
        p_ui_path = PC_DATA_DIR / rel
        if not p_ui_path.exists():
            continue
        bak = BACKUP_DIR / rel
        if not bak.exists():
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(v_ui_path, bak)
        v_bytes = bak.read_bytes()
        p_bytes = p_ui_path.read_bytes()
        out_bytes = convert_single_sheet_pc_to_vita(v_bytes, p_bytes, zero_origins={0, 1, 2, 3})
        v_ui_path.write_bytes(out_bytes)
        ui_cnt += 1

    # 2. All Dungeon/st*/Data.pck entry[0] (floor entry title banner Texture)
    data_cnt = 0
    for v_data_path in sorted((VITA_APP_DIR / "Dungeon").glob("st*/Data.pck")):
        rel = v_data_path.relative_to(VITA_APP_DIR)
        p_data_path = PC_DATA_DIR / rel
        if not p_data_path.exists():
            continue
        # Read current v_data_path (which already has converted English event strings in entry[1..N])
        cur_v_bytes = v_data_path.read_bytes()
        _, _, v_entries = read_pck_entries(cur_v_bytes)
        _, _, p_entries = read_pck_entries(p_data_path.read_bytes())
        if v_entries and p_entries and v_entries[0].startswith(b"Texture"):
            v_entries[0] = convert_single_sheet_pc_to_vita(v_entries[0], p_entries[0], zero_origins={0})
            v_data_path.write_bytes(build_pck_from_template(cur_v_bytes, v_entries))
            data_cnt += 1

    print(f"Patched {ui_cnt} Dungeon/st*/UI.tex and {data_cnt} Dungeon/st*/Data.pck[0] textures")


def _morton_transform(src: bytes, w: int, h: int, bpp: int, swizzle: bool) -> bytes:
    """Apply Morton (Z-order) swizzle (swizzle=True) or unswizzle (swizzle=False)."""
    dst = bytearray(len(src))

    def compact1by1(x: int) -> int:
        x &= 0x55555555
        x = (x ^ (x >> 1)) & 0x33333333
        x = (x ^ (x >> 2)) & 0x0F0F0F0F
        x = (x ^ (x >> 4)) & 0x00FF00FF
        x = (x ^ (x >> 8)) & 0x0000FFFF
        return x

    min_dim = min(w, h)
    log2_min = min_dim.bit_length() - 1
    mask = (1 << (log2_min * 2)) - 1
    for i in range(w * h):
        low = i & mask
        high = i >> (log2_min * 2)
        y = compact1by1(low)
        x = compact1by1(low >> 1)
        if w >= h:
            x |= high << log2_min
        else:
            y |= high << log2_min
        lin_off = (y * w + x) * bpp
        swz_off = i * bpp
        if swizzle:
            dst[swz_off : swz_off + bpp] = src[lin_off : lin_off + bpp]
        else:
            dst[lin_off : lin_off + bpp] = src[swz_off : swz_off + bpp]
    return bytes(dst)


def unswizzle_morton(src: bytes, w: int, h: int, bpp: int = 4) -> bytes:
    return _morton_transform(src, w, h, bpp, swizzle=False)


def swizzle_morton(src: bytes, w: int, h: int, bpp: int = 4) -> bytes:
    return _morton_transform(src, w, h, bpp, swizzle=True)


def map_vita_ui_part_to_pc(vi: int) -> tuple[int, int] | None:
    """Return (pc_sheet_idx, pc_part_idx) for Vita UI.tex part index vi."""
    if 0 <= vi <= 255:
        return (0, vi)
    if 256 <= vi <= 278:
        return (3, vi - 256)
    if 279 <= vi <= 303:
        return (0, 256 + (vi - 279))
    if 304 <= vi <= 324:
        return (0, 281 + (vi - 304))
    if 325 <= vi <= 411:
        return (0, 435 + (vi - 325))
    if 412 <= vi <= 480:
        return (3, 23 + (vi - 412))
    if 481 <= vi <= 553:
        return (0, 522 + (vi - 481))
    if 554 <= vi <= 707:
        return (1, vi - 554)
    if 708 <= vi <= 752:
        return (2, 59 + (vi - 708))
    if 753 <= vi <= 811:
        return (2, vi - 753)
    if 812 <= vi <= 818:
        return (3, 92 + (vi - 812))
    if 819 <= vi <= 821:
        return (7, vi - 819)
    if 822 <= vi <= 902:
        return (3, 99 + (vi - 822))
    if 903 <= vi <= 974:
        return (3, 196 + (vi - 903))
    if vi == 975:
        return (4, 0)
    if vi == 976:
        return (4, 1)
    if vi == 977:
        return (5, 0)
    if vi == 978:
        return (6, 0)
    if 979 <= vi <= 994:
        return (3, 180 + (vi - 979))
    return None


def patch_main_ui_tex() -> None:
    rel = Path("UI.tex")
    vp = VITA_APP_DIR / rel
    bak = BACKUP_DIR / rel
    if not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vp, bak)

    v_ui = bak.read_bytes()
    t_off = v_ui.find(b"Texture             ")
    chunk_sz, flags, data_sz, vw, vh = struct.unpack_from("<5I", v_ui, t_off + 20)
    swiz_img = Image.open(io.BytesIO(v_ui[t_off + 40 : t_off + 40 + data_sz]))
    print(f"Unswizzling Vita UI.tex ({vw}x{vh})...")
    unswiz_raw = unswizzle_morton(swiz_img.tobytes(), vw, vh, 4)
    v_img = Image.frombytes("RGBA", (vw, vh), unswiz_raw)

    vp_off = v_ui.find(b"Parts               ")
    vc = struct.unpack_from("<I", v_ui, vp_off + 24)[0]
    v_parts = [list(struct.unpack_from("<8f", v_ui, vp_off + 28 + i * 32)) for i in range(vc)]
    a_off = v_ui.find(b"Anime               ")
    v_anime_tail = v_ui[a_off:]

    # Load all 8 PC UI.pck sheets and downscale each by 0.5x
    _, _, p_entries = read_pck_entries((PC_DATA_DIR / "UI.pck").read_bytes())
    p_sheets: list[tuple[Image.Image, list[tuple[float, ...]], int, int]] = []
    for e in p_entries:
        p_img, p_pts, _ = decode_pc_tex(e)
        pw, ph = p_img.size
        p_sheets.append((p_img, p_pts, pw, ph))

    replaced = 0
    for vi in range(vc):
        m = map_vita_ui_part_to_pc(vi)
        if m is None:
            continue
        s_idx, pi = m
        p_img, p_pts, pw, ph = p_sheets[s_idx]
        vx, vy, vpw, vph, vu0, vv0, vu1, vv1 = v_parts[vi]
        px, py, ppw, pph, pu0, pv0, pu1, pv1 = p_pts[pi]

        vx0 = int(round(vu0 * vw))
        vy0 = int(round(vv0 * vh))
        vx1 = int(round(vu1 * vw))
        vy1 = int(round(vv1 * vh))
        vw_box = vx1 - vx0
        vh_box = vy1 - vy0
        if vw_box <= 0 or vh_box <= 0:
            continue

        px0 = int(round(pu0 * pw))
        py0 = int(round(pv0 * ph))
        px1 = int(round(pu1 * pw))
        py1 = int(round(pv1 * ph))
        if px1 <= px0 or py1 <= py0:
            continue

        crop = p_img.crop((px0, py0, px1, py1))
        tw = max(1, int(round((px1 - px0) * 0.5)))
        th = max(1, int(round((py1 - py0) * 0.5)))

        # Fit inside Vita's allocated atlas box (vw_box x vh_box) so it never bleeds into adjacent sprites
        fit_w = min(tw, vw_box)
        fit_h = min(th, vh_box)
        scaled = crop.resize((fit_w, fit_h), Image.Resampling.LANCZOS)

        # Clear Vita's original box and paste the English sprite at (vx0, vy0)
        clear_box = Image.new("RGBA", (vw_box, vh_box), (0, 0, 0, 0))
        v_img.paste(clear_box, (vx0, vy0))
        v_img.paste(scaled, (vx0, vy0))

        # Update Part w, h, u1, v1 to match fit_w, fit_h while preserving Vita's origin alignment
        if vx != 0.0:
            v_parts[vi][0] = round(fit_w * 0.5, 2)
        if vy != 0.0:
            v_parts[vi][1] = round(fit_h * 0.5, 2)
        v_parts[vi][2] = float(fit_w)
        v_parts[vi][3] = float(fit_h)
        v_parts[vi][6] = (vx0 + fit_w) / float(vw)
        v_parts[vi][7] = (vy0 + fit_h) / float(vh)
        replaced += 1

    # Swizzle back to Morton order and save with flags = 0x81034000 (hardware PS Vita parity)
    print(f"Swizzling Vita UI.tex ({vw}x{vh})...")
    swiz_raw = swizzle_morton(v_img.tobytes(), vw, vh, 4)
    swiz_out_img = Image.frombytes("RGBA", (vw, vh), swiz_raw)
    buf = io.BytesIO()
    swiz_out_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    out_ui = build_vita_tex(png_bytes, vw, vh, [tuple(p) for p in v_parts], v_anime_tail, flags=0x81034000)
    vp.write_bytes(out_ui)
    print(f"Patched UI.tex ({replaced}/{vc} parts replaced, Morton PNG {len(png_bytes)} bytes, flags=0x81034000)")


def patch_misc_textures() -> None:
    """Port GameOver.tex, Title/UI_23.tex, WorldMap.tex, and WorldMap/wm*_parts.tex."""
    pairs = [
        (Path("GameOver.tex"), Path("GameOver.tex")),
        (Path("Title/UI_23.tex"), Path("Title/UI_23.tex")),
        (Path("WorldMap.tex"), Path("WorldMap/WorldMap.tex")),
        (Path("WorldMap/wm01_parts.tex"), Path("WorldMap/wm01_parts.tex")),
        (Path("WorldMap/wm02_parts.tex"), Path("WorldMap/wm02_parts.tex")),
        (Path("WorldMap/wm03_parts.tex"), Path("WorldMap/wm03_parts.tex")),
    ]
    cnt = 0
    for v_rel, p_rel in pairs:
        vp = VITA_APP_DIR / v_rel
        pp = PC_DATA_DIR / p_rel
        if not vp.exists() or not pp.exists():
            continue
        bak = BACKUP_DIR / v_rel
        if not bak.exists():
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vp, bak)
        out_b = convert_single_sheet_pc_to_vita(bak.read_bytes(), pp.read_bytes())
        vp.write_bytes(out_b)
        cnt += 1
    print(f"Patched {cnt} standalone textures (GameOver, Title/UI_23, WorldMap)")


def patch_cg_pck() -> None:
    """Append converted ENEMY_NAME_*, EVT_NAME_*, and BATTLETEACHER_* textures from PC CG_EN.pck to Vita CG.pck and update Pack table."""
    vp = VITA_APP_DIR / "CG.pck"
    pp = PC_DATA_DIR / "CG_EN.pck"
    bak = BACKUP_DIR / "CG.pck"
    if not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        print("Backing up original CG.pck (701 MB)...")
        shutil.copy2(vp, bak)
    else:
        # Restore clean header/size from backup before appending
        shutil.copy2(bak, vp)

    def read_header(path: Path) -> tuple[int, int, list[str], list[tuple[int, int]]]:
        with path.open("rb") as f:
            hdr = f.read(262144)
        f_off = hdr.find(b"Filename            ")
        p_off = hdr.find(b"Pack                ")
        _, p_cnt = struct.unpack_from("<II", hdr, p_off + 20)
        names = []
        for i in range(p_cnt):
            n_rel = struct.unpack_from("<I", hdr, f_off + 24 + i * 4)[0]
            cur = f_off + 24 + n_rel
            end = hdr.find(b"\x00", cur)
            names.append(hdr[cur:end].decode("ascii", errors="ignore"))
        offs = [struct.unpack_from("<II", hdr, p_off + 28 + i * 8) for i in range(p_cnt)]
        return f_off, p_off, names, offs

    _, v_p_off, v_names, v_offs = read_header(vp)
    _, _, p_names, p_offs = read_header(pp)
    p_map = {n: o for n, o in zip(p_names, p_offs) if n}

    updated = 0
    with vp.open("r+b") as vf, pp.open("rb") as pf:
        vf.seek(0, io.SEEK_END)
        cur_end = vf.tell()
        pad = (-cur_end) % 16
        if pad:
            vf.write(b"\x00" * pad)
            cur_end += pad

        for idx, name in enumerate(v_names):
            if not name or name not in p_map:
                continue
            if not (name.startswith("ENEMY_NAME_") or name.startswith("EVT_NAME_") or name.startswith("BATTLETEACHER_")):
                continue
            vo, vs = v_offs[idx]
            po, ps = p_map[name]
            vf.seek(vo)
            v_tex = vf.read(vs)
            pf.seek(po)
            p_tex = pf.read(ps)

            new_tex = convert_single_sheet_pc_to_vita(v_tex, p_tex)
            new_off = cur_end
            new_sz = len(new_tex)
            vf.seek(new_off)
            vf.write(new_tex)
            cur_end = new_off + new_sz
            pad = (-cur_end) % 16
            if pad:
                vf.write(b"\x00" * pad)
                cur_end += pad

            v_offs[idx] = (new_off, new_sz)
            updated += 1

        # Write updated Pack table in place
        for idx, (no, ns) in enumerate(v_offs):
            vf.seek(v_p_off + 28 + idx * 8)
            vf.write(struct.pack("<II", no, ns))

    print(f"Patched CG.pck ({updated} ENEMY_NAME / EVT_NAME / BATTLETEACHER textures ported)")


def _map_vita_title_part_to_pc(vi: int) -> int | None:
    """Map Vita Title.tex part index (0..63) to PC Title.tex part index (0..44)."""
    if 0 <= vi <= 26:
        return vi
    if 27 <= vi <= 35:
        return vi + 1  # Skip PC Part[27] ('Quit Game' pink)
    if vi == 36:
        return 38
    if vi in (38, 39):
        return vi + 2
    if vi in (61, 62):
        return vi - 19
    if vi == 63:
        return 44
    return None


def patch_title_assets() -> None:
    """Port Title/Title.tex (mapped parts), Title/SEV.pck (235), and Title/Event.pck (87 matching)."""
    # 1. Title/Title.tex
    rel_tex = Path("Title/Title.tex")
    vp = VITA_APP_DIR / rel_tex
    bak = BACKUP_DIR / rel_tex
    if not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vp, bak)

    v_tex = bak.read_bytes()
    t_off = v_tex.find(b"Texture             ")
    _, flags, data_sz, vw, vh = struct.unpack_from("<5I", v_tex, t_off + 20)
    v_img = Image.open(io.BytesIO(v_tex[t_off + 40 : t_off + 40 + data_sz])).convert("RGBA")

    vp_off = v_tex.find(b"Parts               ")
    vc = struct.unpack_from("<I", v_tex, vp_off + 24)[0]
    v_parts = [list(struct.unpack_from("<8f", v_tex, vp_off + 28 + i * 32)) for i in range(vc)]
    a_off = v_tex.find(b"Anime               ")
    v_anime_tail = v_tex[a_off:]

    p_img, p_parts, _ = decode_pc_tex((PC_DATA_DIR / rel_tex).read_bytes())
    pw, ph = p_img.size

    replaced = 0
    for vi in range(vc):
        pi = _map_vita_title_part_to_pc(vi)
        if pi is None:
            continue
        vx, vy, vpw, vph, vu0, vv0, vu1, vv1 = v_parts[vi]
        px, py, ppw, pph, pu0, pv0, pu1, pv1 = p_parts[pi]

        vx0, vy0 = int(round(vu0 * vw)), int(round(vv0 * vh))
        vx1, vy1 = int(round(vu1 * vw)), int(round(vv1 * vh))
        vw_box, vh_box = vx1 - vx0, vy1 - vy0
        if vw_box <= 0 or vh_box <= 0:
            continue

        px0, py0 = int(round(pu0 * pw)), int(round(pv0 * ph))
        px1, py1 = int(round(pu1 * pw)), int(round(pv1 * ph))
        pw_box, ph_box = px1 - px0, py1 - py0
        if pw_box <= 0 or ph_box <= 0:
            continue

        fit_w = min(vw_box, max(1, int(round(pw_box * 0.5))))
        fit_h = min(vh_box, max(1, int(round(ph_box * 0.5))))
        crop = p_img.crop((px0, py0, px1, py1)).resize((fit_w, fit_h), Image.Resampling.LANCZOS)
        v_img.paste((0, 0, 0, 0), (vx0, vy0, vx1, vy1))
        v_img.paste(crop, (vx0, vy0))
        if vx != 0.0:
            v_parts[vi][0] = round(fit_w * 0.5, 2)
        if vy != 0.0:
            v_parts[vi][1] = round(fit_h * 0.5, 2)
        v_parts[vi][2] = float(fit_w)
        v_parts[vi][3] = float(fit_h)
        v_parts[vi][6] = (vx0 + fit_w) / float(vw)
        v_parts[vi][7] = (vy0 + fit_h) / float(vh)
        replaced += 1

    buf = io.BytesIO()
    v_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    vp.write_bytes(build_vita_tex(png_bytes, vw, vh, [tuple(p) for p in v_parts], v_anime_tail, flags=0x81014000))
    print(f"Patched Title/Title.tex ({replaced}/{vc} parts replaced, linear PNG {len(png_bytes)} bytes)")

    # 2. Title/SEV.pck and Title/Event.pck
    for rel_pck in (Path("Title/SEV.pck"), Path("Title/Event.pck")):
        vp_pck = VITA_APP_DIR / rel_pck
        bak_pck = BACKUP_DIR / rel_pck
        if not bak_pck.exists():
            bak_pck.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vp_pck, bak_pck)

        vb = bak_pck.read_bytes()
        pb = (PC_DATA_DIR / rel_pck).read_bytes()
        _, vc_pck, v_entries = read_pck_entries(vb)
        _, _, p_entries = read_pck_entries(pb)
        new_entries = [
            convert_single_sheet_pc_to_vita(ve, pe)
            for ve, pe in zip(v_entries, p_entries[:vc_pck])
        ]
        vp_pck.write_bytes(build_pck_from_template(vb, new_entries))
        print(f"Patched {rel_pck.as_posix()} ({len(new_entries)}/{vc_pck} entries ported)")


def main() -> None:
    patch_character_pck()
    patch_dungeon_textures()
    patch_misc_textures()
    patch_title_assets()
    patch_cg_pck()
    patch_main_ui_tex()
    print("All textures patched successfully.")


if __name__ == "__main__":
    main()
