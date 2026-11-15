#!/usr/bin/env python3
"""Rename the project in one step (fork-friendly). Standard library only.

    python3 scripts/rename.py Homebase               # slug becomes "homebase"
    python3 scripts/rename.py "Tangent Crew" --slug tangent-crew --dry-run

What changes:
  - the display name in the README title, LICENSE holder and the architecture image source
  - the slug everywhere else (skill name, skill folder, install paths, clone commands)
  - the skill folder skills/<old-slug>/ moves to skills/<new-slug>/

What it does NOT do: rename the GitHub repository, re-render PNG images
(it lists the image sources that changed), or touch installed teams.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CURRENT_SLUG = "cornermen"
TEXT_SUFFIXES = {".md", ".py", ".json", ".html", ".txt", ".toml", ".yml", ".yaml", ".cfg"}
TEXT_NAMES = {"LICENSE"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")

# (file, pattern, replacement template) where the display name is wanted instead of the slug.
DISPLAY_RULES = [
    ("README.md", re.compile(r"^# {old}$", re.M), "# {display}"),
    ("LICENSE", re.compile(r"{old} contributors"), "{display} contributors"),
    ("docs/assets/src/architecture.html", re.compile(r">{old}</text>"), ">{display}</text>"),
]


def slugify(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES):
            yield path


def plan(root: Path, old: str, slug: str, display: str) -> dict[Path, tuple[str, str]]:
    """Return {path: (old_text, new_text)} for every file that changes."""
    changes = {}
    for path in text_files(root):
        before = path.read_text(encoding="utf-8")
        after = before
        rel = path.relative_to(root).as_posix()
        for target, pattern, template in DISPLAY_RULES:
            if rel == target:
                rx = re.compile(pattern.pattern.format(old=re.escape(old)), pattern.flags | re.I)  # title may be the display name
                after = rx.sub(template.format(display=display), after)
        after = after.replace(old.capitalize(), display).replace(old, slug)
        if after != before:
            changes[path] = (before, after)
    return changes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rename the project (display name + slug).")
    ap.add_argument("name", help='display name, e.g. "Homebase"')
    ap.add_argument("--slug", help="repo/skill slug (default: derived from the name)")
    ap.add_argument("--from", dest="old", default=CURRENT_SLUG, help=f"current slug (default {CURRENT_SLUG})")
    ap.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    display = args.name.strip()
    slug = args.slug or slugify(display)
    if not display or not SLUG_RE.match(slug):
        print(f"error: bad slug {slug!r} (lowercase letters, digits, dashes; 3 to 40 chars)", file=sys.stderr)
        return 2
    if slug == args.old:
        print("nothing to do: slug unchanged")
        return 0

    old_skill = root / "skills" / args.old
    new_skill = root / "skills" / slug
    if not old_skill.is_dir():
        print(f"error: {old_skill.relative_to(root)} not found; already renamed? use --from", file=sys.stderr)
        return 2
    if new_skill.exists():
        print(f"error: {new_skill.relative_to(root)} already exists", file=sys.stderr)
        return 2

    changes = plan(root, args.old, slug, display)
    hits = sum(before.count(args.old) for before, _ in changes.values())
    print(f"{args.old} -> {display} (slug {slug}): {len(changes)} files, {hits} occurrences")
    for path in changes:
        print(f"  edit  {path.relative_to(root)}")
    print(f"  move  skills/{args.old}/ -> skills/{slug}/")
    images = [p for p in changes if "assets/src" in p.as_posix()]
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    for path, (_, after) in changes.items():
        path.write_text(after, encoding="utf-8")
    old_skill.rename(new_skill)

    left = [p.relative_to(root).as_posix() for p in text_files(root) if args.old in p.read_text(encoding="utf-8")]
    if left:
        print(f"warning: old slug still present in: {', '.join(left)}", file=sys.stderr)
        return 1
    print("done. Next: run the tests, re-render changed images, rename the GitHub repo.")
    for img in images:
        print(f"  re-render  {img.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
