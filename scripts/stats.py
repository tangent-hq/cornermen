#!/usr/bin/env python3
"""How noisy is the team? Counts scheduled runs vs non-silent responses (sent messages; delivery not verified). Read-only.

    python3 scripts/stats.py                 # last 7 days
    python3 scripts/stats.py --days 30
    python3 scripts/stats.py --json          # machine-readable, for the monthly audit

Reads each profile's cron run transcripts (<hermes home>/profiles/*/cron/output/<job>/*.md)
and job store. A run counts as:
  silent    the agent answered [SILENT] (or nothing), or the job delivers locally only
  script    a no-agent script job (e.g. a backup); listed separately, not counted in the silence rate
  message   a non-silent answer delivered to your messaging app
  approval  a message that starts with "Approve?" (subset of message)
  failed    the run errored, was BLOCKED before the agent started, or reported [CRON_FAILURE]
Runs are grouped by the "[bot:<agent>]" tag in the job name; untagged jobs you added
yourself are grouped under their profile name.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import hermes_home  # noqa: E402

BOT_TAG = re.compile(r"^\[bot:([\w-]+)\]\s*(.*)$")
RUN_TIME = re.compile(r"^\*\*Run Time:\*\*\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)", re.M)
NAME = re.compile(r"^# Cron Job:\s*(.+)$", re.M)


def parse_run(path: Path) -> dict | None:
    text = path.read_text(errors="replace")
    name_m = NAME.search(text)
    if not name_m:
        return None
    when_m = RUN_TIME.search(text)
    when = None
    if when_m:
        raw = when_m.group(1)
        when = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S" if raw.count(":") == 2 else "%Y-%m-%d %H:%M")
    else:  # fall back to the file name: YYYY-MM-DD_HH-MM-SS.md
        try:
            when = datetime.strptime(path.stem, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            return None
    base = {"name": name_m.group(1).strip(), "job_id": path.parent.name, "when": when}
    status = re.search(r"^\*\*Status:\*\*\s*(.+)$", text, re.M)
    if status and "## Response" not in text:
        s = status.group(1).lower()
        bad = any(w in s for w in ("fail", "error", "timeout", "blocked"))
        if "no_agent" in text or "(script)" in text:  # script-only job: housekeeping, not an agent decision
            return {**base, "response": "", "errored": bad, "script": True}
        # an agent run that never started (e.g. BLOCKED before the model ran) is a failure, not silence
        return {**base, "response": "" if "silent" in s else status.group(1), "errored": bad or "silent" not in s}
    head, sep, response = text.partition("\n## Response")
    response = response.strip() if sep else ""
    errored = bool(re.search(r"^## (Error|Failure)", text, re.M)) or response.startswith("[CRON_FAILURE]")
    return {**base, "response": response, "errored": errored or not sep}


def classify(run: dict, deliver: str | None) -> str:
    if run["errored"]:
        return "failed"
    if run.get("script"):
        return "script"
    resp = run["response"]
    if not resp or resp == "[SILENT]" or (deliver or "").lower() in ("local", "none"):
        return "silent"
    return "message"


def collect(home: Path, since: datetime) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for pdir in sorted((home / "profiles").glob("*")):
        jobs_file = pdir / "cron" / "jobs.json"
        deliver = {}
        if jobs_file.exists():
            data = json.loads(jobs_file.read_text() or "{}")
            for j in data.get("jobs", []) if isinstance(data, dict) else data:
                deliver[j.get("id")] = j.get("deliver")
        for f in sorted((pdir / "cron" / "output").glob("*/*.md")):
            run = parse_run(f)
            if not run or run["when"] < since:
                continue
            tag = BOT_TAG.match(run["name"])
            agent, routine = (tag.group(1), tag.group(2)) if tag else (pdir.name, run["name"])
            kind = classify(run, deliver.get(run["job_id"]))  # deleted jobs: judged by the answer alone
            s = stats.setdefault(agent, {"runs": 0, "silent": 0, "message": 0, "approval": 0, "failed": 0, "script": 0,
                                         "messages": []})
            s[kind] += 1
            if kind != "script":
                s["runs"] += 1
            if kind == "message":
                first = run["response"].lstrip("*").strip()
                if first.lower().startswith("approve?"):
                    s["approval"] += 1
                s["messages"].append({"when": run["when"].strftime("%a %d %b %H:%M"), "routine": routine,
                                      "preview": " ".join(run["response"].split())[:90]})
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description="Runs vs messages per agent (read-only).")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true", help="totals only, no message previews")
    args = p.parse_args()
    since = datetime.now() - timedelta(days=args.days)
    stats = collect(hermes_home(), since)

    if args.json:
        print(json.dumps({"days": args.days, "agents": stats}, indent=2))
        return 0
    if not stats:
        print(f"No tagged runs in the last {args.days} days.")
        return 0

    total = {k: sum(s.get(k, 0) for s in stats.values()) for k in ("runs", "silent", "message", "approval", "failed", "script")}
    print(f"\nLast {args.days} days\n")
    width = max(len(a) for a in stats)
    for agent, s in sorted(stats.items(), key=lambda kv: -kv[1]["runs"]):
        extra = f", {s['approval']} approval" if s["approval"] else ""
        fail = f", {s['failed']} failed" if s["failed"] else ""
        fail += f" (+{s['script']} script runs)" if s.get("script") else ""
        print(f"  {agent:<{width}}  {s['runs']:>3} runs  {s['message']:>2} messages{extra}{fail}")
        if not args.quiet:
            for m in s["messages"]:
                print(f"  {'':<{width}}    {m['when']}  {m['routine']}: {m['preview']}")
    rate = 100 * total["silent"] / total["runs"] if total["runs"] else 0
    print(f"\n  {total['runs']} scheduled agent runs, {total['message']} non-silent responses "
          f"({total['approval']} approvals), {rate:.0f}% stayed silent"
          + (f", {total['failed']} failed" if total["failed"] else "") + "."
          + (f" Script-only jobs (not counted): {total['script']}." if total["script"] else "") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
