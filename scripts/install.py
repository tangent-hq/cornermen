#!/usr/bin/env python3
"""Install a team of specialist agents into Hermes, or change an installed team.

Idempotent: re-running never overwrites workspace files you've edited and never
duplicates routines. Personas are re-rendered every run (previous version backed up),
so every agent always knows the current team.

    python3 scripts/install.py --timezone Europe/Berlin                  # starter team
    python3 scripts/install.py --timezone Europe/Berlin --team minimal   # a smaller preset
    python3 scripts/install.py --add finance                             # add a specialist later
    python3 scripts/install.py --remove social                           # pause + drop one
    python3 scripts/install.py --list                                    # presets and agents
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AGENTS_DIR, CORE_AGENT, JOB_PREFIX, REPO, STANDARD_FILES, TEAMS_DIR, Runner, catalog, existing_jobs, is_paused,
    load_agent, load_team, profile_dir, read_registry, render, roster_md, routines_for, say, team_md, write_registry,
)

SKILL_PATH = Path("skills/autonomous-ai-agents/cornermen/SKILL.md")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timezone", help="IANA timezone for every routine, e.g. Europe/Berlin (required on first install)")
    p.add_argument("--workspace", default="~/cornermen", help="shared folder for all agents (default: ~/cornermen)")
    p.add_argument("--team", default="starter", help="preset from teams/ for the first install (default: starter)")
    p.add_argument("--add", default="", help="comma-separated agents to add to the installed team")
    p.add_argument("--remove", default="", help="comma-separated agents to drop (routines paused, files kept)")
    p.add_argument("--clone-from", default=None, help="profile to clone model + API keys from (default: active profile)")
    p.add_argument("--list", action="store_true", help="show presets and available agents, then exit")
    p.add_argument("--dry-run", action="store_true", help="print what would happen, change nothing")
    return p.parse_args()


def show_catalog() -> None:
    say("\nPresets (teams/):")
    for f in sorted(TEAMS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        say(f"  {f.stem:<10} {', '.join(d['agents'])}\n  {'':<10} {d.get('description', '')}")
    say("\nAgents (agents/):")
    for name in catalog():
        s = load_agent(name)
        say(f"  {name:<12} {s['tagline']}{'  (always installed)' if s.get('core') else ''}")
    say("\nYour own: python3 scripts/new-agent.py <name>\n")


def split(csv: str) -> list[str]:
    return [x.strip() for x in csv.split(",") if x.strip()]


def copy_tree(src: Path, dst: Path, values: dict, dry: bool) -> tuple[int, int]:
    created = kept = 0
    if not src.exists():
        return 0, 0
    for f in sorted(src.rglob("*")):
        if f.is_dir():
            continue
        target = dst / f.relative_to(src)
        if target.exists():
            kept += 1
            continue
        created += 1
        if not dry:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(f.read_text(), values))
    return created, kept


def write_new(path: Path, content: str, dry: bool) -> bool:
    if path.exists():
        return False
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return True


def write_with_backup(path: Path, content: str, dry: bool) -> str:
    if path.exists() and path.read_text() == content:
        return "unchanged"
    if dry:
        return "would write"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
    path.write_text(content)
    return "written"


def resolve_team(args, workspace: Path) -> tuple[list[str], list[str], str]:
    """Returns (final team, removed agents, timezone)."""
    installed = read_registry(workspace)
    tz = args.timezone
    if installed:
        tz = tz or json.loads((workspace / "team.json").read_text()).get("timezone")
        team = list(installed)
    else:
        team = [CORE_AGENT] + [a for a in load_team(args.team) if a != CORE_AGENT]
    if not tz:
        raise SystemExit("--timezone is required on the first install (e.g. --timezone Europe/Berlin)")
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise SystemExit(f"unknown timezone: {tz} (use an IANA name like Europe/Berlin)")
    for a in split(args.add):
        load_agent(a)
        if a not in team:
            team.append(a)
    removed = []
    for a in split(args.remove):
        if a == CORE_AGENT:
            raise SystemExit("the coordinator is the core of the team and can't be removed")
        if a in team:
            team.remove(a)
            removed.append(a)
    return team, removed, tz


def main() -> None:
    args = parse_args()
    if args.list:
        show_catalog()
        return
    workspace = Path(args.workspace).expanduser().resolve()
    was_installed = bool(read_registry(workspace))
    team, removed, tz = resolve_team(args, workspace)
    owned = set(read_registry(workspace))
    clashes = [a for a in team if a not in owned and profile_dir(a).exists()]
    if clashes:
        raise SystemExit(f"Hermes profile(s) already exist: {', '.join(clashes)}. Cornermen won't overwrite a profile "
                         f"it didn't create. Rename or delete them (hermes profile delete <name>), then run again.")
    specs = [load_agent(a) for a in team]
    values = {"WORKSPACE": str(workspace), "TIMEZONE": tz, "REPO": str(REPO),
              "INSTALL_DATE": dt.date.today().isoformat(), "ROSTER": roster_md(specs), "TEAM_SIZE": str(len(specs))}
    run = Runner(dry_run=args.dry_run)
    tag = " (dry run)" if args.dry_run else ""
    say(f"\nTeam: {', '.join(team)}{tag}")

    say(f"\n1/4 Workspace -> {workspace}")
    created, kept = copy_tree(REPO / "core" / "workspace", workspace, values, args.dry_run)
    for s in specs:
        c, k = copy_tree(AGENTS_DIR / s["name"] / "files", workspace / s["name"], values, args.dry_run)
        created, kept = created + c, kept + k
        if s.get("core"):
            continue
        for fname, tmpl in STANDARD_FILES.items():
            body = render(tmpl.format(title=s["title"]), values)
            created += write_new(workspace / s["name"] / fname, body, args.dry_run)
        brief = AGENTS_DIR / s["name"] / "brief.md"
        if brief.exists():
            created += write_new(workspace / "shared" / "briefs" / f"{s['name']}.md",
                                 render(brief.read_text(), values), args.dry_run)
    say(f"    {created} files created, {kept} existing files left untouched")
    status = write_with_backup(workspace / "shared" / "team.md", team_md(specs, tz), args.dry_run)
    say(f"    shared/team.md: {status}")

    say("\n2/4 Profiles")
    for s in specs:
        agent = s["name"]
        if profile_dir(agent).exists():
            say(f"    {agent}: exists")
        else:
            clone = ["--clone-from", args.clone_from] if args.clone_from else ["--clone"]
            run.hermes("profile", "create", agent, *clone, "--description", s["description"])
            say(f"    {agent}: created")
        run.hermes("-p", agent, "config", "set", "timezone", tz)
        run.hermes("-p", agent, "config", "set", "cron.mirror_delivery", "true")

    say("\n3/4 Personas (every agent gets the current roster) + coordinator skill")
    rules = (REPO / "core" / "rules.md").read_text()
    for s in specs:
        soul = render((AGENTS_DIR / s["name"] / "SOUL.md").read_text().rstrip() + "\n" + rules, values)
        say(f"    {s['name']}/SOUL.md: {write_with_backup(profile_dir(s['name']) / 'SOUL.md', soul, args.dry_run)}")
    skill = render((REPO / "skills" / "cornermen" / "SKILL.md").read_text(), values)
    say(f"    coordinator skill: {write_with_backup(profile_dir(CORE_AGENT) / SKILL_PATH, skill, args.dry_run)}")

    say("\n4/4 Routines (new ones are created paused)")
    for s in specs:
        agent = s["name"]
        have = {j.get("name") for j in existing_jobs(agent)}
        wanted = routines_for(s)
        added = 0
        for job in wanted:
            name = JOB_PREFIX.format(agent=agent) + job["slug"]
            if name in have:
                continue
            cmd = ["-p", agent, "cron", "create", job["schedule"], render(job["prompt"], values),
                   "--name", name, "--deliver", job["deliver"], "--workdir", str(workspace),
                   "--paused", "--paused-reason", "waiting for onboarding (scripts/activate.py)"]
            if job.get("repeat"):
                cmd += ["--repeat", str(job["repeat"])]
            run.hermes(*cmd)
            added += 1
        say(f"    {agent}: {added} added, {len(wanted) - added} already present")
    for agent in removed:
        paused = 0
        for job in existing_jobs(agent):
            if job.get("name", "").startswith(JOB_PREFIX.format(agent=agent)) and not is_paused(job):
                run.hermes("-p", agent, "cron", "pause", job["id"])
                paused += 1
        say(f"    {agent}: removed from the team, {paused} routines paused (profile and files kept)")

    if not args.dry_run:
        workspace.mkdir(parents=True, exist_ok=True)
        write_registry(workspace, team, tz)

    if was_installed:
        say(f"\nDone{tag}. New specialists start paused.\n"
            "Tell your coordinator what changed: it runs their kickoff and asks\n"
            "before switching their routines on (or: python3 scripts/activate.py).\n")
        return
    say(f"""
Done{tag}. Next steps (about 10 minutes):

  1. Give each agent its own messaging bot. In the Hermes desktop app:
     Messaging > Telegram > one bot per profile ({', '.join(team)}).
     One token per profile: two profiles on one token collide.
  2. Restart the gateway so it picks up the timezones:   hermes gateway restart
  3. Check everything:                                  python3 scripts/doctor.py
  4. Say hi to your coordinator. It asks for one long brain dump
     (a voice note is perfect), fills in {workspace}/shared/,
     and introduces the specialists one per day.
  5. When the coordinator asks to switch routines on, say yes
     (or run: python3 scripts/activate.py).
""")


if __name__ == "__main__":
    main()
