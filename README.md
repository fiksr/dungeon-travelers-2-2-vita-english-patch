# Dungeon Travelers 2-2 — PS Vita (`PCSG00841`) English Backport Patch

Ports the official English localization from the PC release of **Dungeon Travelers 2-2: The Fallen Maidens and the Book of Beginnings** to the Japanese PS Vita release (**`PCSG00841`**).

## What Is Translated
- **Story, Events, Dungeon Dialogue & Shops (`Script\*.pck`, `Dungeon\Dungeon.pck`, `Dungeon\st*\Data.pck`):**
  - All `17` `Script\*.pck` files (`12,314` dialogue blocks), all `21` dungeon map scripts (`Dungeon\st*\Data.pck`), and `Dungeon\Dungeon.pck` converted with proportional line wrapping (`56` chars/line) and auto-paged dialogue boxes.
- **Items, Skills, Classes, Quests, Monsters & System Strings (`Parameter\*.pck`, `Enemy\Enemy.pck`, `NPC\NPC.pck`, `Summon\Summon.pck`):**
  - All `30` `Parameter\*.pck` databases (`StringData.pck`, `ItemData.pck`, `EquipmentData.pck`, `MagicSkillData.pck`, `PassiveSkillData.pck`, `PartySkillData.pck`, `TechniqueSkillData.pck`, `UniqueSkillData.pck`, `JoinSkillData.pck`, `ClassData.pck`, `QuestData.pck`, `SealScrollData.pck`, `TrophyData.pck`, etc.).
- **Character Profiles, Nameplates & Dungeon Chatter (`Character\Character.pck`):**
  - All `19` playable characters' `PlayerData.txt`, upper-left dungeon exploration speech bubble chatter (`sub[-2]`), and English portrait nameplates (`sub[-1]`).
- **Executable & Proportional Font Engine (`eboot.bin`, `Font24.fnt`, `Font30.fnt`):**
  - Patched `CStringBase::init` (`0x810B98FC`) from `52` to `104` chars/line and `CStringBase::SetString` centering loops (`0x810BAC60`, `0x810BAE48`) to match.
  - Added per-character proportional ASCII advance table (`6px..18px` for `Font30`, `5px..14px` for `Font24`) via free `.text` code cave (`0x81345920..0x813459F0`) while keeping the `PT_SCE_RELA` jump table (`0x810BA6FC`) intact for `A_button` / `B_button` / `x_button` controller icons.
- **UI, Title Screen, World Map & Dungeon Banner Textures:**
  - `UI.tex` (`995 / 1008` parts ported from PC `UI.pck`, Morton-swizzled RGBA8888 PNG with `flags = 0x81034000` for real PS Vita GXM hardware parity).
  - `Title\Title.tex` (`42 / 64` title screen & gallery button sprites), `Title\UI_23.tex`, `Title\SEV.pck` (`235 / 235`), `Title\Event.pck` (`87 / 87`).
  - All `20` `Dungeon\st*\UI.tex` & `Data.pck[0]` stage banners (`8-pixel` GXM stride-aligned widths), `WorldMap.tex`, `WorldMap\wm*_parts.tex`, and `GameOver.tex`.
- **Enemy / Event / Tutorial Graphic Overlays (`CG.pck` — Full Zip):**
  - `889` English `ENEMY_NAME_*`, `EVT_NAME_*`, and `BATTLETEACHER_*` textures ported into `CG.pck` while keeping all original uncensored PS Vita event CG artwork untouched.

---

## Installation Guide (Full vs. Lite)

Download either `.zip` from the **[Releases](https://github.com/fiksr/dungeon-travelers-2-2-vita-english-patch/releases)** page:

| Package | Size | What's Included | When to Choose |
| :--- | :--- | :--- | :--- |
| **`DungeonTravelers2-2_PCSG00841_EN_Patch_Full.zip`** | `516.6 MB` | All `106` translated files **+ patched `CG.pck`** (`889` English enemy nameplates, event title cards, and Battle Teacher tutorial slides, with original uncensored Vita event CGs preserved) | Recommended if you want 100% of graphic overlays and tutorials in English. |
| **`DungeonTravelers2-2_PCSG00841_EN_Patch_Lite.zip`** | `19.8 MB` | All `106` translated files (`eboot.bin`, fonts, all story/dungeon scripts, items/skills/parameters, `UI.tex`, `Title\*`, `Character.pck`, `Dungeon\st*`, `WorldMap\*`) — **excludes `CG.pck`** | Recommended if you want a fast ~20 MB download; 100% of story, menus, skills, items, and dungeon chatter are in English (only the graphic enemy/tutorial overlays stored inside `CG.pck` stay Japanese). |

### How to Install (Both Full & Lite Use the Exact Same Steps)

All files sit directly at the root of the `.zip` (no nested wrapper folder):

- **Vita3K Emulator:**
  1. Right-click **Dungeon Travelers 2-2 (`PCSG00841`)** in Vita3K -> **Open Folder** (opens `<Vita3K>\ux0\app\PCSG00841\`).
  2. Extract all files from the `.zip` (either **Full** or **Lite**) directly into `<Vita3K>\ux0\app\PCSG00841\` and click **Replace the files in the destination** when prompted.

- **Real PS Vita (`rePatch`):**
  1. Make sure you have the `rePatch` plugin (`rePatch reDux0` / `reLoaded`) installed on your PS Vita.
  2. Create the folder `ux0:rePatch/PCSG00841/` on your Vita if it does not exist.
  3. Extract all files from the `.zip` (either **Full** or **Lite**) directly into `ux0:rePatch/PCSG00841/`.

---

## Building From Source

1. Place your clean Japanese PS Vita `PCSG00841` dump in `backup\PCSG00841\` (or point `VITA_APP_DIR` to `ux0\app\PCSG00841`) and the PC English release `Data\ENG` folder in `DungeonTravelers2-2_EN\Data\ENG\`.
2. Run the patch scripts inside `scripts\`:
   ```bash
   python scripts/patch_fonts.py
   python scripts/patch_eboot.py
   python scripts/convert_scripts.py
   python scripts/patch_parameters.py
   python scripts/patch_textures.py
   python scripts/build_release.py
   ```
