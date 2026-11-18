"""Build both pure copy-paste release .zip packages with files at the root of the zip (no outer PCSG00841/ folder)."""
from pathlib import Path
import shutil
import zipfile

ROOT_DIR = Path(r"C:\Users\Nikola\Desktop\AI PROJECTS\DungeonTravelers2-2")
VITA_APP_DIR = Path(r"C:\Users\Nikola\AppData\Roaming\Vita3K\Vita3K\ux0\app\PCSG00841")
BACKUP_DIR = ROOT_DIR / "backup" / "PCSG00841"
RELEASE_DIR = ROOT_DIR / "release"

LITE_ZIP = ROOT_DIR / "DungeonTravelers2-2_PCSG00841_EN_Patch_Lite.zip"
FULL_ZIP = ROOT_DIR / "DungeonTravelers2-2_PCSG00841_EN_Patch_Full.zip"

README_TXT = """Dungeon Travelers 2-2 (PCSG00841) - English Localization Patch
================================================================

Installation (Vita3K):
  1. Extract all files from this .zip directly into your PCSG00841 game folder:
       <Vita3K>\\ux0\\app\\PCSG00841\\
     and overwrite existing files when prompted.

Installation (Real PS Vita with rePatch):
  1. Extract all files from this .zip directly into:
       ux0:rePatch/PCSG00841/
"""


def main() -> None:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    total_bytes = 0
    for bak_file in sorted(BACKUP_DIR.rglob("*")):
        if not bak_file.is_file():
            continue
        rel = bak_file.relative_to(BACKUP_DIR)
        if rel.name == "CG.pck":
            continue
        src = VITA_APP_DIR / rel
        if not src.exists():
            continue
        dst = RELEASE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        total_bytes += dst.stat().st_size

    readme_path = RELEASE_DIR / "README.txt"
    readme_path.write_text(README_TXT, encoding="utf-8")

    # 1. Build Option B: Lite Copy-Paste Zip (files at root of zip, without CG.pck)
    print(f"Building Lite zip: {LITE_ZIP.name} ...")
    with zipfile.ZipFile(LITE_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(RELEASE_DIR.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(RELEASE_DIR))
    lite_mb = LITE_ZIP.stat().st_size / 1024 / 1024
    print(f"  Lite zip built: {LITE_ZIP} ({lite_mb:.2f} MB)")

    # 2. Build Option A: Full Copy-Paste Zip (files at root of zip, including CG.pck)
    print(f"Building Full zip: {FULL_ZIP.name} ...")
    shutil.copy2(LITE_ZIP, FULL_ZIP)
    cg_src = VITA_APP_DIR / "CG.pck"
    with zipfile.ZipFile(FULL_ZIP, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(cg_src, Path("CG.pck"))
    full_mb = FULL_ZIP.stat().st_size / 1024 / 1024
    print(f"  Full zip built: {FULL_ZIP} ({full_mb:.2f} MB)")


if __name__ == "__main__":
    main()
