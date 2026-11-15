#!/usr/bin/env python3
"""A tiny stand-in for the `hermes` CLI, used by the tests.

Implements just enough of `profile create`, `config set` and `cron create/pause/resume`
to exercise install.py, activate.py and doctor.py against a temp HERMES_HOME_ROOT.
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

root = Path(os.environ["HERMES_HOME_ROOT"])
args = sys.argv[1:]
with open(root / "calls.log", "a") as log:
    log.write(json.dumps(args) + "\n")

profile = "default"
if args[:1] == ["-p"]:
    profile, args = args[1], args[2:]
pdir = root / "profiles" / profile


def jobs_file():
    f = pdir / "cron" / "jobs.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


def load():
    f = jobs_file()
    return json.loads(f.read_text()) if f.exists() else {"jobs": []}


def strict_parser(prog, positionals, flags, switches):
    """Mirror the real CLI's option surface (Hermes Agent v0.21 `--help`), so an unknown flag fails here too."""
    p = argparse.ArgumentParser(prog=prog, exit_on_error=False, add_help=False)
    for name, nargs in positionals:
        p.add_argument(name, nargs=nargs)
    for f in flags:
        p.add_argument(f)
    for s in switches:
        p.add_argument(s, action="store_true")
    return p


PROFILE_CREATE = strict_parser(
    "profile create", [("profile_name", None)], ["--clone-from", "--description"],
    ["--clone", "--clone-all", "--clone-channels", "--sync-imports", "--no-alias", "--no-skills"])
CRON_CREATE = strict_parser(
    "cron create", [("schedule", None), ("prompt", "?")],
    ["--name", "--deliver", "--failure-deliver", "--repeat", "--skill", "--script", "--monitor-script",
     "--monitor-url", "--workdir", "--model", "--provider", "--reasoning-effort", "--interpreter",
     "--paused-reason"],
    ["--no-agent", "--pin", "--continuity", "--paused"])
KNOWN_CONFIG_KEYS = {"timezone", "cron.mirror_delivery"}


def parse(parser, argv):
    try:
        ns, extra = parser.parse_known_args(argv)
    except argparse.ArgumentError as e:
        sys.exit(f"fake hermes: {e}")
    if extra:
        sys.exit(f"fake hermes: unrecognized arguments {extra}")
    return ns


if args[:2] == ["profile", "create"]:
    ns = parse(PROFILE_CREATE, args[2:])
    d = root / "profiles" / ns.profile_name
    d.mkdir(parents=True)
    (d / "SOUL.md").write_text("default soul\n")
    (d / "config.yaml").write_text("model: test\n")
elif args[:2] == ["config", "set"]:
    key, val = args[2], args[3]
    if key not in KNOWN_CONFIG_KEYS:
        sys.exit(f"fake hermes: unknown config key {key}")
    cfg = pdir / "config.yaml"
    line = f"timezone: {val}\n" if key == "timezone" else f"cron:\n  mirror_delivery: {val}\n"
    cfg.write_text((cfg.read_text() if cfg.exists() else "") + line)
elif args[:2] == ["cron", "create"]:
    ns = parse(CRON_CREATE, args[2:])
    data = load()
    data["jobs"].append({
        "id": uuid.uuid4().hex[:12], "name": ns.name, "schedule": ns.schedule, "prompt": ns.prompt,
        "deliver": ns.deliver, "workdir": ns.workdir, "paused_reason": ns.paused_reason,
        "state": "paused" if ns.paused else "scheduled", "enabled": not ns.paused,
    })
    jobs_file().write_text(json.dumps(data))
elif args[:1] == ["cron"] and args[1] in ("pause", "resume"):
    data = load()
    for j in data["jobs"]:
        if j["id"] == args[2]:
            j["state"] = "paused" if args[1] == "pause" else "scheduled"
            j["enabled"] = args[1] == "resume"
    jobs_file().write_text(json.dumps(data))
else:
    sys.exit(f"fake hermes: unsupported {args}")
