"""Port PC EN Parameter/*.pck and Character/Character.pck (PlayerData.txt) to Vita PCSG00841."""
from pathlib import Path
import shutil
import struct

PC_DATA_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\DungeonTravelers2-2_EN\Data\ENG")
VITA_APP_DIR = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841")
BACKUP_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\backup\PCSG00841")

PC_PARAM_DIR = PC_DATA_DIR / "Parameter"
VITA_PARAM_DIR = VITA_APP_DIR / "Parameter"
BACKUP_PARAM_DIR = BACKUP_DIR / "Parameter"


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


def patch_character_pck() -> None:
    """Repack Character/Character.pck replacing sub[0] (PlayerData.txt) with PC EN while keeping Vita sub[1..4] (NamePlate.tex PNGs)."""
    rel = Path("Character/Character.pck")
    vp = VITA_APP_DIR / rel
    pp = PC_DATA_DIR / rel
    bak = BACKUP_DIR / rel
    bak.parent.mkdir(parents=True, exist_ok=True)
    if not bak.exists():
        shutil.copy2(vp, bak)

    vb = bak.read_bytes()
    pb = pp.read_bytes()
    _, vc, v_chars = read_pck_entries(vb)
    _, pc, p_chars = read_pck_entries(pb)
    if vc != pc:
        raise RuntimeError(f"Character.pck count mismatch: {vc} vs {pc}")

    new_chars = []
    for v_sub_pck, p_sub_pck in zip(v_chars, p_chars):
        _, _, v_subs = read_pck_entries(v_sub_pck)
        _, _, p_subs = read_pck_entries(p_sub_pck)
        # Replace sub[0] (PlayerData.txt) with PC English, keep Vita sub[1..4] (binary + PNG NamePlate.tex)
        merged_subs = [p_subs[0]] + v_subs[1:]
        new_chars.append(build_pck_from_template(v_sub_pck, merged_subs))

    out_b = build_pck_from_template(vb, new_chars)
    vp.write_bytes(out_b)
    print(f"Repacked Character/Character.pck ({vc} playable character PlayerData.txt entries ported)")


def main() -> None:
    patch_character_pck()

    for rel in [Path("NPC/NPC.pck"), Path("Enemy/Enemy.pck"), Path("Summon/Summon.pck")]:
        vp = VITA_APP_DIR / rel
        pp = PC_DATA_DIR / rel
        bak = BACKUP_DIR / rel
        bak.parent.mkdir(parents=True, exist_ok=True)
        if not bak.exists():
            shutil.copy2(vp, bak)
        shutil.copy2(pp, vp)
        print(f"Copied {rel}")

    BACKUP_PARAM_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for vp in sorted(VITA_PARAM_DIR.glob("*.pck")):
        bak = BACKUP_PARAM_DIR / vp.name
        if not bak.exists():
            shutil.copy2(vp, bak)

        pp = PC_PARAM_DIR / vp.name
        if not pp.exists():
            continue

        vb = bak.read_bytes()
        pb = pp.read_bytes()
        _, vc, _ = read_pck_entries(vb)
        _, pc, p_entries = read_pck_entries(pb)

        if vp.name == "CharacterData.pck":
            # Binary 8-byte entries; Vita has 232 entries vs PC 250
            print(f"Skipped {vp.name} (binary stats: Vita={vc}, PC={pc})")
            continue
        elif vp.name == "StringData.pck":
            # Keep Vita's 634 entries and convert literal '\n' (0x5C 0x6E) in string bodies to 0x0A
            fixed_entries = []
            for entry in p_entries[:vc]:
                if len(entry) > 16 and b"\\n" in entry[16:]:
                    body = entry[16:].rstrip(b"\x00").replace(b"\\n", b"\n") + b"\x00"
                    raw = bytearray(entry[:16] + body)
                    pad = (-len(raw)) % 8
                    if pad:
                        raw.extend(b"\x00" * pad)
                    fixed_entries.append(bytes(raw))
                else:
                    fixed_entries.append(entry)
            out_b = build_pck_from_template(vb, fixed_entries)
            vp.write_bytes(out_b)
            print(f"Repacked {vp.name}: ported {vc}/{pc} entries (fixed literal \\n) -> {vp.name}")
            copied += 1
        elif vc == pc:
            shutil.copy2(pp, vp)
            copied += 1
            print(f"Copied {vp.name} ({vc} entries)")
        else:
            print(f"WARNING skipped {vp.name}: entry count mismatch ({vc} vs {pc})")

    print(f"Done: updated Character/Character.pck + {copied} Parameter/*.pck files.")


if __name__ == "__main__":
    main()
