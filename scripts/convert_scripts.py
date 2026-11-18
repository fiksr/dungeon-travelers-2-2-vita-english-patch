"""Convert PC EN Script/*.pck, Dungeon/Dungeon.pck, and Dungeon/st*/Data.pck (.adv.bin) to Vita PCSG00841."""
from pathlib import Path
import re
import shutil
import struct
import textwrap

PC_DATA_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\DungeonTravelers2-2_EN\Data\ENG")
VITA_APP_DIR = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841")
BACKUP_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\backup\PCSG00841")

WRAP_WIDTH = 50


def normalize_text(s: str) -> str:
    return (
        s.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
        .replace("\u00a0", " ")
    )


def wrap_and_encode_sjis(text: str, single_line: bool = False) -> bytes:
    text = normalize_text(text)
    flat = re.sub(r"[ \t]*\n[ \t]*", " ", text.strip())
    if single_line:
        return flat.encode("cp932", errors="replace")

    wrapped = textwrap.wrap(flat, width=WRAP_WIDTH, break_long_words=False, break_on_hyphens=True)
    for w in (53, 56, 59, 62, 65):
        if len(wrapped) <= 3:
            break
        wrapped = textwrap.wrap(flat, width=w, break_long_words=False, break_on_hyphens=True)

    if not wrapped:
        wrapped = [flat]
    elif len(wrapped) > 3:
        wrapped = [wrapped[0], wrapped[1], " ".join(wrapped[2:])]

    joined = "\n".join(wrapped)
    return joined.encode("cp932", errors="replace")


def convert_adv_bin(adv: bytes) -> tuple[bytes, int]:
    """Find all string opcodes (<op2> 0a <u32_id> ff ff ff <str>\\x00) and convert them."""
    out = bytearray()
    pos = 0
    count = 0
    n = len(adv)
    target_ops = {b"\x22\x01\x0a", b"\x73\x01\x0a", b"\x27\x02\x0a", b"\x00\x00\x0a"}
    while pos < n:
        idx = adv.find(b"\xff\xff\xff", pos + 7)
        if idx < 0:
            out.extend(adv[pos:])
            break
        op_start = idx - 7
        op = adv[op_start : op_start + 3]
        if op not in target_ops:
            out.extend(adv[pos : idx + 3])
            pos = idx + 3
            continue

        nul = adv.find(b"\x00", idx + 3)
        if nul < 0:
            out.extend(adv[pos:])
            break

        out.extend(adv[pos : idx + 3])
        raw_str = adv[idx + 3 : nul]
        try:
            txt = raw_str.decode("utf-8")
        except UnicodeDecodeError:
            try:
                txt = raw_str.decode("cp932")
            except UnicodeDecodeError:
                txt = raw_str.decode("utf-8", errors="replace")

        if " " in txt or "\n" in txt or any(ord(c) > 127 for c in txt):
            out.extend(wrap_and_encode_sjis(txt, single_line=(op == b"\x00\x00\x0a")))
            count += 1
        else:
            out.extend(raw_str)
        out.append(0)
        pos = nul + 1
    return bytes(out), count


def parse_pck(b: bytes) -> tuple[int, int, list[str], list[bytes]]:
    p_off = b.find(b"Pack                ")
    if p_off < 0:
        raise RuntimeError("No Pack chunk")
    cnt = struct.unpack_from("<I", b, p_off + 24)[0]
    first_off = struct.unpack_from("<I", b, p_off + 28)[0] if cnt > 0 else len(b)
    names = []
    if b.startswith(b"Filename            "):
        for i in range(cnt):
            noff = struct.unpack_from("<I", b, 28 + i * 4)[0]
            end = b.find(b"\x00", noff)
            names.append(b[noff:end].decode("ascii", errors="replace"))
    else:
        names = [f"entry_{i}" for i in range(cnt)]
    entries = []
    for i in range(cnt):
        off, sz = struct.unpack_from("<II", b, p_off + 28 + i * 8)
        entries.append(b[off : off + sz])
    return p_off, first_off, names, entries


def build_pck(template_b: bytes, new_entries: list[bytes]) -> bytes:
    p_off = template_b.find(b"Pack                ")
    cnt = struct.unpack_from("<I", template_b, p_off + 24)[0]
    if cnt == 0:
        return template_b
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


def convert_pck_bytes(vita_b: bytes, pc_b: bytes) -> tuple[bytes, int]:
    """Recursively convert a .pck archive, preserving Vita Texture/binary entries and porting PC scripts/DungeonData.txt."""
    _, _, v_names, v_entries = parse_pck(vita_b)
    _, _, p_names, p_entries = parse_pck(pc_b)
    if len(v_entries) == 0:
        return vita_b, 0

    p_by_name = {n: e for n, e in zip(p_names, p_entries) if n}
    out_entries = []
    str_total = 0

    for i, (vn, ve) in enumerate(zip(v_names, v_entries)):
        pe = p_entries[i] if (i < len(p_entries) and len(v_entries) == len(p_entries)) else p_by_name.get(vn)
        if pe is None:
            out_entries.append(ve)
            continue

        if ve.startswith(b"Texture             "):
            # Always keep Vita's PNG texture instead of PC's LZ77 texture
            out_entries.append(ve)
        elif ve.startswith(b"Filename            ") and b"Pack                " in ve:
            conv_sub, c = convert_pck_bytes(ve, pe)
            out_entries.append(conv_sub)
            str_total += c
        elif pe.startswith(b"[Dungeon]"):
            out_entries.append(pe)
            str_total += 1
        elif b"\x22\x01\x0a" in pe or b"\x73\x01\x0a" in pe or b"\x27\x02\x0a" in pe or vn.endswith(".adv.bin"):
            conv_adv, c = convert_adv_bin(pe)
            out_entries.append(conv_adv)
            str_total += c
        else:
            out_entries.append(ve)

    return build_pck(vita_b, out_entries), str_total


def process_file(rel_path: Path) -> None:
    pc_p = PC_DATA_DIR / rel_path
    vita_p = VITA_APP_DIR / rel_path
    bak_p = BACKUP_DIR / rel_path
    if not vita_p.exists() or not pc_p.exists():
        return
    bak_p.parent.mkdir(parents=True, exist_ok=True)
    if not bak_p.exists():
        shutil.copy2(vita_p, bak_p)

    vita_b = bak_p.read_bytes()
    pc_b = pc_p.read_bytes()
    out_b, str_total = convert_pck_bytes(vita_b, pc_b)
    vita_p.write_bytes(out_b)
    print(f"{str(rel_path):28s}: {str_total:5d} strings/entries converted")


def main() -> None:
    print("=== Converting Script/*.pck ===")
    for p in sorted((PC_DATA_DIR / "Script").glob("*.pck")):
        process_file(p.relative_to(PC_DATA_DIR))

    print("\n=== Converting Dungeon/Dungeon.pck & Dungeon/st*/Data.pck ===")
    process_file(Path("Dungeon/Dungeon.pck"))
    for p in sorted((PC_DATA_DIR / "Dungeon").glob("st*/Data.pck")):
        process_file(p.relative_to(PC_DATA_DIR))


if __name__ == "__main__":
    main()
