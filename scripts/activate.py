#!/usr/bin/env python3
"""Switch the team's routines on (or off again).

    python3 scripts/activate.py                  # resume every routine except onboarding kickoffs
    python3 scripts/activate.py --agent finance  # only one specialist
    python3 scripts/activate.py --pause          # pause them all again
    python3 scripts/activate.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import JOB_PREFIX, KICKOFF_SLUG, Runner, existing_jobs, installed_agents, is_paused, say  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", default="~/cornermen")
    p.add_argument("--agent", default=None, help="only this agent")
    p.add_argument("--pause", action="store_true", help="pause the routines instead of resuming them")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    agents = installed_agents(Path(args.workspace).expanduser())
    if args.agent:
        if args.agent not in agents:
            raise SystemExit(f"'{args.agent}' is not on the installed team: {', '.join(agents)}")
        agents = [args.agent]
    run = Runner(dry_run=args.dry_run)
    verb = "pause" if args.pause else "resume"
    changed = 0
    for agent in agents:
        prefix = JOB_PREFIX.format(agent=agent)
        for job in existing_jobs(agent):
            name = job.get("name", "")
            if not name.startswith(prefix) or name == prefix + KICKOFF_SLUG:
                continue
            if is_paused(job) == args.pause:
                continue
            run.hermes("-p", agent, "cron", verb, job["id"])
            say(f"  {verb}d  {name}")
            changed += 1
    say(f"\n{changed} routines {verb}d." + ("" if changed else " Nothing to do."))


if __name__ == "__main__":
    main()
