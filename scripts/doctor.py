#!/usr/bin/env python3
"""Health check for the installed team. Read-only.

    python3 scripts/doctor.py [--workspace ~/cornermen]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    JOB_PREFIX, existing_jobs, is_paused, load_agent, profile_dir, read_registry, routines_for,
)

OK, WARN, FAIL = "\033[32m✔\033[0m", "\033[33m!\033[0m", "\033[31m✘\033[0m"
MESSAGING_KEYS = ("TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "SLACK_BOT_TOKEN", "SIGNAL_ACCOUNT")


def env_has_key(env: Path, keys: tuple[str, ...]) -> bool:
    """True if any key is set to a non-empty value. Never reads values into output."""
    if not env.exists():
        return False
    for line in env.read_text().splitlines():
        m = re.match(r"\s*([A-Z_]+)\s*=\s*(\S+)", line)
        if m and m.group(1) in keys:
            return True
    return False


TOKEN_STALE_DAYS = 6  # Google revokes refresh tokens of "Testing" OAuth apps after 7 days


def calendar_token_status(pdir: Path, now: float | None = None) -> tuple[str, str] | None:
    """Offline check of the google-workspace token. None if no calendar is connected.

    The token file is rewritten on every successful refresh, so its age is the time since
    the calendar last worked. Never prints token contents."""
    tok = pdir / "google_token.json"
    if not tok.exists():
        return None
    try:
        tok.read_text()
    except OSError:
        return FAIL, "calendar token unreadable"
    age = ((now if now is not None else time.time()) - tok.stat().st_mtime) / 86400
    if age >= TOKEN_STALE_DAYS:
        return WARN, (f"calendar token last refreshed {age:.0f} days ago: probably expired. Re-run the "
                      "google-workspace auth, and publish your OAuth app to Production (Testing-mode "
                      "tokens die after 7 days)")
    return OK, f"calendar token refreshed {age:.1f} days ago"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", default="~/cornermen")
    ws = Path(p.parse_args().workspace).expanduser()
    problems = 0

    print(f"\nWorkspace  {ws}")
    team = read_registry(ws)
    if not team or not (ws / "shared" / "system.md").exists():
        print(f"  {FAIL} no team installed here (run scripts/install.py)")
        return 1
    print(f"  {OK} team of {len(team)}: {', '.join(team)}")
    templates = sorted(str(f.relative_to(ws)) for f in ws.rglob("*.md") if "TEMPLATE: not filled in" in f.read_text())
    shared_left = [t for t in templates if t.startswith("shared/")]
    print(f"  {OK if not shared_left else WARN} {len(templates)} files still TEMPLATE ({len(shared_left)} in shared/)")

    for agent in team:
        spec = load_agent(agent)
        pdir = profile_dir(agent)
        print(f"\n{agent}")
        if not pdir.exists():
            print(f"  {FAIL} profile missing")
            problems += 1
            continue
        soul = (pdir / "SOUL.md").read_text() if (pdir / "SOUL.md").exists() else ""
        good = "## Standing rules" in soul and str(ws.resolve()) in soul
        print(f"  {OK if good else FAIL} SOUL.md {'rendered for this workspace' if good else 'missing or points elsewhere'}")
        problems += not good
        stale = [o for o in team if f"(`{o}`)" not in soul]
        if good and stale:
            print(f"  {WARN} persona doesn't know about: {', '.join(stale)} (re-run install.py)")

        cfg = (pdir / "config.yaml").read_text() if (pdir / "config.yaml").exists() else ""
        tz = re.search(r"^timezone:\s*['\"]?([\w/+-]+)", cfg, re.M)
        print(f"  {OK if tz else FAIL} timezone {tz.group(1) if tz else 'not set (cron would run in host time)'}")
        problems += not tz
        mirror = re.search(r"mirror_delivery:\s*true", cfg)
        print(f"  {OK if mirror else WARN} cron.mirror_delivery {'on' if mirror else 'off (replies lose context)'}")

        msg = env_has_key(pdir / ".env", MESSAGING_KEYS)
        print(f"  {OK if msg else WARN} messaging bot {'configured' if msg else 'not configured yet'}")

        cal = calendar_token_status(pdir)
        if cal:
            print(f"  {cal[0]} {cal[1]}")

        jobs = {j.get("name"): j for j in existing_jobs(agent)}
        want = [JOB_PREFIX.format(agent=agent) + r["slug"] for r in routines_for(spec) if r.get("kind") != "kickoff"]
        present = [n for n in want if n in jobs]
        active = [n for n in present if not is_paused(jobs[n])]
        mark = OK if len(present) == len(want) else FAIL
        problems += len(present) != len(want)
        print(f"  {mark} routines {len(present)}/{len(want)} present, {len(active)} active")

    print(f"\n{'All good. (Offline structure check: does not test live bots, tokens or delivery.)' if not problems else f'{problems} problem(s) found.'}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
