from __future__ import annotations

import os
from pathlib import Path


SOURCE_REPO = Path("/home/wilson/CEP_NA_BOLSA")
OUTPUT_FILE = Path("00_Strategy/00_Legacy_Imports/LEGACY_BUNDLE.md")
IGNORE_DIRS = {"node_modules", ".git", "venv", "__pycache__", "site-packages"}


def is_eligible_md(source_root: Path, file_path: Path) -> bool:
    if file_path.suffix.lower() != ".md":
        return False

    rel = file_path.relative_to(source_root)
    rel_posix = "/" + rel.as_posix().lower()
    in_docs = "/docs/" in rel_posix
    name = file_path.name.lower()
    has_state_or_transfer = ("state" in name) or ("transfer" in name)
    return in_docs or has_state_or_transfer


def collect_files(source_root: Path) -> list[Path]:
    matched: list[Path] = []
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            if is_eligible_md(source_root, path):
                matched.append(path)
    matched.sort()
    return matched


def build_bundle(files: list[Path], source_root: Path, target_file: Path) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with target_file.open("w", encoding="utf-8") as out:
        for path in files:
            rel = path.relative_to(source_root).as_posix()
            out.write(f"--- FILE: {rel} ---\n")
            out.write(path.read_text(encoding="utf-8", errors="ignore"))
            out.write("\n\n")


def main() -> None:
    files = collect_files(SOURCE_REPO)
    build_bundle(files, SOURCE_REPO, OUTPUT_FILE)

    print("TASK T017 - LEGACY MD BUNDLE")
    print("")
    print("BUNDLED FILES")
    if not files:
        print("- NONE")
    else:
        for path in files:
            print(f"- {path.relative_to(SOURCE_REPO).as_posix()}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if OUTPUT_FILE.exists() else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
