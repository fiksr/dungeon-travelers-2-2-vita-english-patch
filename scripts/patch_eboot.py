"""Patch PCSG00841 app0.elf:
1. Disable UI-sprite hijack for ' ' (0x20), 'A' (0x41), 'B' (0x42), 'x' (0x78) in 0x810BA6FC jump table.
2. Scale ASCII (r8==0, r7<0x80) character advance r6 by 9/16 (30->16px, 24->13px) in-place at 0x810BA8A8..0x810BA8C4.
3. Pack modified ELF into FSELF eboot.bin.
"""
from pathlib import Path
import shutil
import struct
import zlib

ORIG_ELF = Path(r"C:\Users\Nikola\Desktop\Vita3K\elfdumps\PCSG00841\0x81000000-0x81347E50_app0.elf")
BACKUP_EBOOT = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2\backup\PCSG00841\eboot.bin")
OUT_EBOOT = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841\eboot.bin")


def build_fself(orig_self: bytes, elf_bytes: bytes, out_path: Path) -> int:
    hdr_len = struct.unpack_from("<Q", orig_self, 0x10)[0]
    out = bytearray(orig_self[:hdr_len])
    e_phnum = struct.unpack_from("<H", elf_bytes, 44)[0]
    out[0xA0 : 0xA0 + 0x34] = elf_bytes[0:0x34]
    out[0xE0 : 0xE0 + e_phnum * 0x20] = elf_bytes[0x34 : 0x34 + e_phnum * 0x20]

    cur_off = hdr_len
    for i in range(e_phnum):
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from(
            "<8I", elf_bytes, 0x34 + i * 32
        )
        seg_raw = bytes(elf_bytes[p_offset : p_offset + p_filesz])
        seg_z = zlib.compress(seg_raw, 6)
        pad = (16 - (cur_off % 16)) % 16
        out.extend(b"\x00" * pad)
        cur_off += pad
        seg_off = cur_off
        out.extend(seg_z)
        cur_off += len(seg_z)
        struct.pack_into("<QQIIII", out, 0x180 + i * 32, seg_off, len(seg_z), 2, 0, 2, 0)

    struct.pack_into("<Q", out, 0x18, len(elf_bytes))
    struct.pack_into("<Q", out, 0x20, len(out))
    out_path.write_bytes(out)
    return len(out)


def main() -> None:
    if not BACKUP_EBOOT.exists():
        BACKUP_EBOOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT_EBOOT, BACKUP_EBOOT)

    elf = bytearray(ORIG_ELF.read_bytes())

    # 1. In CStringBase::init (0x810B98FC): change lsr r4, r0, #3 (r5 * 2 = 52 chars/line)
    #    to lsr r4, r0, #2 (r5 * 4 = 104 chars/line) so lines > 52 chars are never truncated.
    #    Also update the two centering loops in CStringBase::SetString (0x810BAC60 and 0x810BAE48)
    #    from lsr #4 (dividing r4 by 2) to lsr #5 (dividing r4 by 4) so centered text boxes
    #    recover the exact original box width r5 * [fp, #0x14].
    struct.pack_into("<I", elf, 0xE0 + 0xB98FC, 0xE1A04120)
    struct.pack_into("<I", elf, 0xE0 + 0xBAC60, 0xE1A012A1)
    struct.pack_into("<I", elf, 0xE0 + 0xBAE48, 0xE1A002A0)

    # 2. Leave the PT_SCE_RELA-relocated jump table at 0x810BA6FC..0x810BA85C untouched!
    #    At 0x810BA6E4, branch unconditionally to 0x810BA8A8 (b #0x810ba8a8 = 0xEA00006F)
    #    so all ASCII 0x20..0x7E (' ', 'A', 'B', 'x', '(', ')', '-', '0'..'9') render as font glyphs.
    struct.pack_into("<I", elf, 0xE0 + 0xBA6E4, 0xEA00006F)
    struct.pack_into("<I", elf, 0xE0 + 0xBA6EC, 0xE3520019)
    struct.pack_into("<I", elf, 0xE0 + 0xBA860, 0xEA000010)

    # 3. At 0x810BA8A8..0x810BA8C8:
    #      0x810BA8A8: cmp   r7, #0x80            -> 0xE3570080 (true iff ASCII < 0x80)
    #      0x810BA8AC: addlo r6, r6, #1           -> 0x32866001 (r6 + 1)
    #      0x810BA8B0: lsrlo r6, r6, #1           -> 0x31A060A6 ((r6 + 1) >> 1: 27->14px, 24->12px)
    #      0x810BA8B4: b     #0x810ba8bc          -> 0xEA000000 (skip 0x810BA8B8)
    #      0x810BA8B8: b     #0x810ba8a8          -> 0xEAFFFFFA (ORIGINAL passthrough branch!)
    #      0x810BA8BC: str   r7, [r5]             -> 0xE5857000
    #      0x810BA8C0: mov   r0, r8               -> 0xE1A00008
    #      0x810BA8C4: str   r6, [r4]             -> 0xE5846000
    #      0x810BA8C8: pop   {r4-r8, pc}          -> 0xE8BD81F0
    hook_insns = [
        0xE3570080,
        0x32866001,
        0x31A060A6,
        0xEA000000,
        0xEAFFFFFA,
        0xE5857000,
        0xE1A00008,
        0xE5846000,
        0xE8BD81F0,
    ]
    hook_off = 0xE0 + 0xBA8A8
    for i, w in enumerate(hook_insns):
        struct.pack_into("<I", elf, hook_off + i * 4, w)
    print("Patched 0x810B98FC (104 chars/line), 0x810BA6E4, and 0x810BA8A8..0x810BA8C8 (14px/12px ASCII advance)")

    orig_self = BACKUP_EBOOT.read_bytes()
    sz = build_fself(orig_self, bytes(elf), OUT_EBOOT)
    print(f"Wrote FSELF eboot.bin ({sz} bytes) -> {OUT_EBOOT}")


if __name__ == "__main__":
    main()
