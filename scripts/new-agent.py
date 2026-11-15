#!/usr/bin/env python3
"""Scaffold your own specialist from agents/_template/.

    python3 scripts/new-agent.py finance --title Finance --tagline "budget, savings, investing"
    # edit agents/finance/SOUL.md, brief.md and agent.json, then:
    python3 scripts/install.py --add finance
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AGENTS_DIR, NAME_RE, say  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="profile name: lowercase letters, digits, hyphens (e.g. finance)")
    p.add_argument("--title", help="display name (default: the name, capitalized)")
    p.add_argument("--tagline", default="(the area this specialist owns)", help="what it owns, in a few words")
    p.add_argument("--asks-on", default="Wednesday", help="when it may ask the user questions")
    args = p.parse_args()

    if not NAME_RE.match(args.name):
        raise SystemExit("name must be lowercase letters, digits or hyphens, 2 to 31 characters, starting with a letter")
    dest = AGENTS_DIR / args.name
    if dest.exists():
        raise SystemExit(f"agents/{args.name} already exists")
    title = args.title or args.name.replace("-", " ").title()
    subs = {"__NAME__": args.name, "__TITLE__": title, "__TAGLINE__": args.tagline, "__ASKS_ON__": args.asks_on}

    shutil.copytree(AGENTS_DIR / "_template", dest)
    for f in dest.rglob("*"):
        if f.is_file() and f.suffix in {".md", ".json"}:
            text = f.read_text()
            for k, v in subs.items():
                text = text.replace(k, json.dumps(v)[1:-1] if f.suffix == ".json" else v)
            f.write_text(text)
    say(f"""Created agents/{args.name}/

  agent.json   title, tagline, message budget, routines (one weekly check to start)
  SOUL.md      persona: role, owned files, behavior, style
  brief.md     copied to shared/briefs/{args.name}.md; the coordinator fills it during onboarding
  files/       area files copied into the workspace folder {args.name}/

Next: edit those three files, then
  python3 scripts/install.py --add {args.name}
""")


if __name__ == "__main__":
    main()
