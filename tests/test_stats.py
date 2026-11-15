"""stats.py: counts runs vs messages from cron transcripts in a fake Hermes home."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def transcript(name, when, response=None, script_status=None):
    head = f"# Cron Job: {name}\n\n**Job ID:** x\n**Run Time:** {when:%Y-%m-%d %H:%M:%S}\n"
    if script_status:
        return head + f"**Mode:** no_agent (script)\n**Status:** {script_status}"
    return head + f"\n## Prompt\n\nprompt text\n\n**Response Characters:** 1\n## Response\n\n{response}\n"


class StatsTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.now = datetime.now() - timedelta(hours=1)

    def add(self, profile, job_id, name, deliver="telegram", **kw):
        out = self.home / "profiles" / profile / "cron" / "output" / job_id
        out.mkdir(parents=True, exist_ok=True)
        jobs_file = self.home / "profiles" / profile / "cron" / "jobs.json"
        jobs = json.loads(jobs_file.read_text())["jobs"] if jobs_file.exists() else []
        if job_id not in {j["id"] for j in jobs}:
            jobs.append({"id": job_id, "name": name, "deliver": deliver})
        jobs_file.write_text(json.dumps({"jobs": jobs}))
        when = kw.pop("when", self.now)
        (out / f"{when:%Y-%m-%d_%H-%M-%S}.md").write_text(transcript(name, when, **kw))

    def stats(self, *args):
        env = {**os.environ, "HERMES_HOME_ROOT": str(self.home)}
        res = subprocess.run([sys.executable, str(REPO / "scripts" / "stats.py"), "--json", *args],
                             env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)["agents"]

    def test_classifies_runs(self):
        self.add("coordinator", "a1", "[bot:coordinator] Weekly review", response="Here is the plan.")
        self.add("coordinator", "a2", "[bot:coordinator] Backup", script_status="silent (empty output)")
        self.add("builder", "b1", "[bot:builder] Build session", response="[SILENT]")
        self.add("builder", "b2", "[bot:builder] Monday", response="**Approve?** Flip the repo public.")
        self.add("builder", "b3", "radar", deliver="local", response="5 new items logged")
        self.add("fitness", "f1", "[bot:fitness] Check-in", response="[CRON_FAILURE]\nchild failed")
        s = self.stats()
        # the no-agent backup is a script run: listed, but not an agent run and not "silent"
        self.assertEqual((s["coordinator"]["runs"], s["coordinator"]["message"], s["coordinator"]["silent"],
                          s["coordinator"]["script"]), (1, 1, 0, 1))
        self.assertEqual(s["builder"]["runs"], 3)  # untagged 'radar' grouped under its profile
        self.assertEqual((s["builder"]["message"], s["builder"]["approval"], s["builder"]["silent"]), (1, 1, 2))
        self.assertEqual(s["fitness"]["failed"], 1)

    def test_blocked_preflight_counts_as_failed(self):
        out = self.home / "profiles" / "fitness" / "cron" / "output" / "f9"
        out.mkdir(parents=True)
        (out / f"{self.now:%Y-%m-%d_%H-%M-%S}.md").write_text(
            f"# Cron Job: [bot:fitness] Friday planning input\n\n**Job ID:** f9\n**Run Time:** {self.now:%Y-%m-%d %H:%M:%S}\n"
            "**Status:** BLOCKED (configuration)\n\nThe pre-run configuration check found a problem, so the agent did not run.\n")
        s = self.stats()["fitness"]
        self.assertEqual((s["runs"], s["failed"], s["silent"]), (1, 1, 0))

    def test_window(self):
        self.add("vision", "v1", "[bot:vision] Question", response="old", when=self.now - timedelta(days=10))
        self.add("vision", "v1", "[bot:vision] Question", response="new")
        self.assertEqual(self.stats("--days", "7")["vision"]["message"], 1)
        self.assertEqual(self.stats("--days", "14")["vision"]["message"], 2)


if __name__ == "__main__":
    unittest.main()
