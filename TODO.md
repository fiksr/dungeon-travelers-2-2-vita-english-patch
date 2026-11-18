# Dungeon Travelers 2-2 (PCSG00841) English Port — Remaining TODOs

## 1. [DONE] Upper-Left Dungeon Chatter Speech Bubble (`そう`, etc.)
- **Resolution:** Confirmed `Character\Character.pck` `sub[-2]` (49 occurrences of `そう`) holds the dungeon chatter/bark table with an identical binary header/offset layout between PC and Vita. Updated `patch_character_pck()` in `scripts\patch_textures.py` to merge `p_subs[:-1] + [ported_ui_tex]` and verified `0` occurrences of `そう` remain in `Character\Character.pck`.

## 2. [DONE] Title Screen Menu Graphics (`Title\Title.tex`, `Title\Event.pck`, `Title\SEV.pck`)
- **Resolution:** Added `_map_vita_title_part_to_pc()` and `patch_title_assets()` in `scripts\patch_textures.py`, mapping 42/64 Vita `Title\Title.tex` parts (`968×1686`, `flags=0x81014000`, skipping PC `Part[27]` `Quit Game` so `Part[27..35]` blue buttons align 1:1 with `Part[28..36]`), porting `235/235` `Title\SEV.pck` entries, and porting `87/87` matching `Title\Event.pck` entries.

## 3. [DONE] Re-Swizzle `UI.tex` (`flags = 0x81034000`) for 100% Real PS Vita Hardware Parity
- **Resolution:** Refactored `unswizzle_morton()` into `_morton_transform()` + `unswizzle_morton()` / `swizzle_morton()` in `scripts\patch_textures.py`, and updated `patch_main_ui_tex()` to save Morton-swizzled PNG (`4,346,230` bytes) with `flags=0x81034000`. Verified `unswizzle_morton()` round-trip.

## 4. [DONE] Package Pure Copy-Paste GitHub Release Zips
- **Resolution:** Updated `scripts\build_release.py` to output two pure extract-and-overwrite `.zip` packages (no `.bat` or Python needed):
  - `DungeonTravelers2-2_PCSG00841_EN_Patch_Lite.zip`: `PCSG00841\` (`106` non-CG modified files) + `README.txt`.
  - `DungeonTravelers2-2_PCSG00841_EN_Patch_Full.zip`: `PCSG00841\` (`106` files + patched `CG.pck`) + `README.txt`.

