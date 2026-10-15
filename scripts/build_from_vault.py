#!/usr/bin/env python3
"""Refresh this repo from the live skill and the vault kit. Run before every commit.

    python3 -I scripts/build_from_vault.py [--dry-run]

Copies, never deletes:
  ~/.claude/skills/neighborhood-report/SKILL.md            -> skills/neighborhood-report/SKILL.md
  <vault>/Neighborhood Map Lite/scripts/*.py, template*.html -> skills/neighborhood-report/scripts/lite/
  <vault>/Neighborhood Map Lite/README.md                  -> skills/neighborhood-report/reference/lite-kit.md
                                                              (Obsidian frontmatter, [[wikilinks]] and artifact links stripped)
Client folders, client data, photos, run reviews and anything under Brain/Private never come in: only the files
named above are read. Then run scripts/check_secrets.sh.
"""
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_SRC = Path.home() / ".claude/skills/neighborhood-report/SKILL.md"
KIT = Path.home() / "Obsidian-Vault/Brain/Real Estate/Market Intel/Neighborhood Map Lite"
DEST = REPO / "skills/neighborhood-report"
DRY = "--dry-run" in sys.argv


def put(src, dst, text=None):
    print(("would copy " if DRY else "copy ") + "%s -> %s" % (src, dst.relative_to(REPO)))
    if DRY:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if text is None:
        shutil.copyfile(src, dst)
    else:
        dst.write_text(text, encoding="utf-8")


def clean_markdown(text):
    text = re.sub(r"\A---\n.*?\n---\n+", "", text, flags=re.S)                 # Obsidian frontmatter
    text = re.sub(r"\s*\((?:private link )?https://claude\.ai/artifact/[^)]*\)", "", text)  # client artifact links
    text = re.sub(r"https://claude\.ai/artifact/\S+", "(private client page)", text)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)                 # [[target|label]] -> label
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)                              # [[target]] -> target
    return text


def main():
    put(SKILL_SRC, DEST / "SKILL.md")
    for f in sorted((KIT / "scripts").iterdir()):
        if f.suffix == ".py" or (f.suffix == ".html" and f.name.startswith("template")):
            put(f, DEST / "scripts/lite" / f.name)
    readme = KIT / "README.md"
    put(readme, DEST / "reference/lite-kit.md", clean_markdown(readme.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
