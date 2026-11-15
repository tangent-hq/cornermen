"""Shared helpers for the team scripts. Standard library only."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / "agents"
TEAMS_DIR = REPO / "teams"
CORE_AGENT = "coordinator"
JOB_PREFIX = "[bot:{agent}] "
KICKOFF_SLUG = "Onboarding kickoff"
PLANNING_SLUG = "Friday planning input"
REGISTRY = "team.json"  # at the workspace root, written by install.py
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")

CAL = "the calendar (if connected; the read command is under Integrations in shared/system.md)"

PLANNING_PROMPT = (
    "Friday planning input (silent). The user plans the weekend and next week with the coordinator on Saturday morning. "
    "Prepare your input: (1) refresh {name}/summary.md (under 20 lines). (2) Overwrite {name}/next-week.md with: a header "
    "'Planning input for weekend + week of <date>'; your time asks for THIS weekend and NEXT week, each as: what, duration, "
    "preferred days/times, fixed or flexible, priority (must/should/nice); then max 2 decisions you need from the user; then "
    "anything the coordinator should know (conflicts, travel, energy). Check " + CAL + " first so the asks fit reality. "
    "Compare this week's log with last week's plan and record what actually happened. {extra}Final response: exactly [SILENT]."
)

KICKOFF_PROMPT = (
    "Onboarding kickoff (one-time). Read {{{{WORKSPACE}}}}/shared/*.md and {{{{WORKSPACE}}}}/shared/briefs/{name}.md. "
    "Fill what you can of your area files in {{{{WORKSPACE}}}}/{name}/ from the shared context; mark anything inferred "
    "'(confirm)' and never invent facts. Write {name}/questions.md: at most 6 ranked questions, one line of why each matters. "
    "Log the kickoff in {name}/log.md. Then output ONLY the message to the user (max 5 lines): one line on who you are and "
    "what you will do for them, then your single most important question. Voice-note answers are welcome; say so."
)

# Every specialist gets these four files; agents/<name>/files/ adds area-specific ones.
STANDARD_FILES = {
    "summary.md": "# {title}: summary\n\n_Kept under ~20 lines. The coordinator and the other agents read this first._\n\n"
                  "Last updated: {{{{INSTALL_DATE}}}}\n\n## Status\n- Not started: waiting for onboarding.\n\n"
                  "## Wins since last review\n-\n\n## Problems / risks\n-\n\n## Next 7 days\n-\n",
    "log.md": "# {title}: log\n\n_Append-only. Newest at the bottom. Use `## YYYY-MM-DD` headings._\n",
    "questions.md": "# {title}: onboarding questions\n\n_Ranked. Asked one at a time. Answers go into the area files._\n\n"
                    "| # | Question | Why it matters | Status |\n|---|---|---|---|\n",
    "next-week.md": "# Planning input\n\n_Overwritten every Friday 20:00 for the coordinator's Saturday planning._\n",
}


# ---------- paths ----------

def hermes_bin() -> str:
    return os.environ.get("HERMES_BIN", "hermes")


def hermes_home() -> Path:
    """The standard Hermes home (~/.hermes). HERMES_HOME_ROOT is a test hook only."""
    if "HERMES_HOME_ROOT" in os.environ:
        return Path(os.environ["HERMES_HOME_ROOT"]).expanduser()
    root = Path.home() / ".hermes"
    custom = os.environ.get("HERMES_HOME")
    if custom:
        home = Path(custom).expanduser().resolve()
        if home != root.resolve() and root.resolve() not in home.parents:
            raise SystemExit(f"HERMES_HOME={custom} is a custom Hermes home. Cornermen supports only the "
                             f"standard ~/.hermes. Unset HERMES_HOME and run again.")
    return root


def profile_dir(agent: str) -> Path:
    return hermes_home() / "profiles" / agent


# ---------- templates ----------

def render(text: str, values: dict[str, str]) -> str:
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    leftover = PLACEHOLDER.findall(text)
    if leftover:
        raise ValueError(f"unrendered placeholders: {sorted(set(leftover))}")
    return text


def catalog() -> list[str]:
    """Every agent definition in agents/ (the scaffold template excluded)."""
    return sorted(p.parent.name for p in AGENTS_DIR.glob("*/agent.json") if not p.parent.name.startswith("_"))


def load_agent(name: str) -> dict:
    path = AGENTS_DIR / name / "agent.json"
    if not path.exists():
        raise SystemExit(f"unknown agent '{name}'. Available: {', '.join(catalog())}. "
                         f"Create your own with: python3 scripts/new-agent.py {name}")
    spec = json.loads(path.read_text())
    spec["name"] = name
    spec.setdefault("planning_input", not spec.get("core", False))
    return spec


def load_team(team: str) -> list[str]:
    path = TEAMS_DIR / f"{team}.json"
    if not path.exists():
        options = ", ".join(sorted(p.stem for p in TEAMS_DIR.glob("*.json")))
        raise SystemExit(f"unknown team '{team}'. Available: {options}")
    return json.loads(path.read_text())["agents"]


def routines_for(spec: dict) -> list[dict]:
    """The agent's own routines plus the standard ones every specialist gets."""
    preamble = (REPO / "core" / "preamble.txt").read_text().strip()
    name = spec["name"]
    out = []
    for r in spec.get("routines", []):
        prompt = r["prompt"] if r.get("preamble") is False else f"{preamble} {r['prompt']}"
        out.append({**r, "prompt": prompt})
    if spec.get("planning_input"):
        out.append({"slug": PLANNING_SLUG, "schedule": "0 20 * * 5", "deliver": "local",
                    "prompt": f"{preamble} " + PLANNING_PROMPT.format(name=name, extra=spec.get("planning_extra", ""))})
    kickoff = spec.get("kickoff") or KICKOFF_PROMPT.format(name=name)
    out.append({"slug": KICKOFF_SLUG, "schedule": "0 9 1 1 *", "deliver": "telegram", "kind": "kickoff",
                "repeat": 1, "prompt": kickoff})
    return out


def roster_md(specs: list[dict]) -> str:
    lines = []
    for s in specs:
        own = "`shared/` and `coordinator/`" if s.get("core") else f"`{s['name']}/`"
        lines.append(f"- **{s['title']}** (`{s['name']}`) owns {own}: {s['tagline']}")
    return "\n".join(lines)


def team_md(specs: list[dict], tz: str) -> str:
    """shared/team.md, regenerated on every install so it always matches the installed team."""
    rows = []
    for s in specs:
        brief = "`system.md`" if s.get("core") else f"`briefs/{s['name']}.md`"
        rows.append(f"| {s['title']} | `{s['name']}` | {s['tagline']} | {brief} |")
    budgets = [f"- **{s['title']}:** {s['budget']}" for s in specs]
    asks = [f"{s['title']}: {s['asks_on']}" for s in specs if not s.get("core")]
    sched = []
    for s in specs:
        items = [f"{r['slug']} `{r['schedule']}` ({'silent' if r['deliver'] == 'local' else 'may message'})"
                 for r in routines_for(s) if r.get("kind") != "kickoff"]
        sched.append(f"- **{s['title']}:** " + "; ".join(items))
    return (
        "# The team\n\n"
        "_Generated by `scripts/install.py` from each agent's `agent.json`. Don't edit by hand: change the agent "
        "definition and re-run the installer, which also refreshes every agent's persona._\n\n"
        f"{len(specs)} agents. Schedules are cron expressions in {tz}.\n\n"
        "| Agent | Hermes profile | Owns | Brief |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        "## Message budgets\nUnprompted messages only; replies to the user don't count.\n" + "\n".join(budgets) + "\n\n"
        "## When each specialist asks questions\n" + ("\n".join(f"- {a}" for a in asks) or "-") + "\n"
        "- During onboarding the coordinator staggers kickoffs: one specialist per day.\n\n"
        "## Routines\n" + "\n".join(sched) + "\n"
    )


# ---------- installed state ----------

def read_registry(workspace: Path) -> list[str]:
    path = workspace / REGISTRY
    if not path.exists():
        return []
    return json.loads(path.read_text())["agents"]


def write_registry(workspace: Path, agents: list[str], tz: str) -> None:
    (workspace / REGISTRY).write_text(json.dumps({"agents": agents, "timezone": tz}, indent=2) + "\n")


def installed_agents(workspace: Path) -> list[str]:
    agents = read_registry(workspace)
    if not agents:
        raise SystemExit(f"no team installed in {workspace} (run scripts/install.py)")
    return agents


def existing_jobs(agent: str) -> list[dict]:
    """Read the profile's job store directly (read-only); mutations go through the CLI."""
    path = profile_dir(agent) / "cron" / "jobs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text() or "{}")
    return data.get("jobs", []) if isinstance(data, dict) else data


def is_paused(job: dict) -> bool:
    return job.get("state") == "paused" or job.get("enabled") is False


class Runner:
    """Runs hermes commands, or prints them in dry-run mode."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def hermes(self, *args: str, check: bool = True) -> subprocess.CompletedProcess | None:
        cmd = [hermes_bin(), *args]
        if self.dry_run:
            print("  $ " + " ".join(shlex.quote(a if len(a) < 90 else a[:87] + "...") for a in cmd))
            return None
        env = {k: v for k, v in os.environ.items() if k != "HERMES_HOME"}  # always target the standard home
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if check and res.returncode != 0:
            sys.stderr.write(res.stdout + res.stderr)
            raise SystemExit(f"command failed: {' '.join(cmd[:4])} ...")
        return res


def say(msg: str) -> None:
    print(msg, flush=True)
