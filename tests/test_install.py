"""End-to-end tests: install, change the team, doctor and activate against a fake hermes CLI."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAKE = REPO / "tests" / "fake_hermes.py"
sys.path.insert(0, str(REPO / "scripts"))
from _common import catalog, load_agent, load_team, routines_for  # noqa: E402

AGENTS = load_team("starter")


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "hermes"
        self.home.mkdir()
        self.ws = self.tmp / "life"
        shim = self.tmp / "hermes-bin"
        shim.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n")
        shim.chmod(0o755)
        self.env = {**os.environ, "HERMES_HOME_ROOT": str(self.home), "HERMES_BIN": str(shim)}

    def run_script(self, name, *args, ok=True):
        res = subprocess.run([sys.executable, str(REPO / "scripts" / name), *args],
                             env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return res

    def install(self, *extra):
        return self.run_script("install.py", "--timezone", "Europe/Berlin", "--workspace", str(self.ws), *extra)

    def change(self, *extra):
        return self.run_script("install.py", "--workspace", str(self.ws), *extra)

    def soul(self, agent):
        return (self.home / "profiles" / agent / "SOUL.md").read_text()

    def jobs(self, agent):
        return json.loads((self.home / "profiles" / agent / "cron" / "jobs.json").read_text())["jobs"]

    def test_existing_profile_is_never_taken_over(self):
        (self.home / "profiles" / "fitness").mkdir(parents=True)
        (self.home / "profiles" / "fitness" / "SOUL.md").write_text("someone else's agent")
        res = self.run_script(
            "install.py", "--timezone", "Europe/Berlin", "--workspace", str(self.ws), ok=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("already exist: fitness", res.stdout + res.stderr)
        self.assertEqual((self.home / "profiles" / "fitness" / "SOUL.md").read_text(), "someone else's agent")
        self.assertFalse(self.ws.exists())
        self.assertFalse((self.home / "profiles" / "coordinator").exists())

    def test_custom_hermes_home_is_refused(self):
        env = {k: v for k, v in self.env.items() if k != "HERMES_HOME_ROOT"}
        env["HOME"] = str(self.tmp)  # never touch the real ~/.hermes
        env["HERMES_HOME"] = "/nonexistent/elsewhere"
        res = subprocess.run([sys.executable, str(REPO / "scripts" / "install.py"), "--timezone", "Europe/Berlin",
                              "--workspace", str(self.ws), "--dry-run"], env=env, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("standard ~/.hermes", res.stdout + res.stderr)

    def test_full_install(self):
        self.install()
        for agent in AGENTS:
            soul = self.soul(agent)
            self.assertIn("## Standing rules", soul)
            self.assertIn(str(self.ws.resolve()), soul)
            self.assertNotRegex(soul, r"\{\{[A-Z_]+\}\}")
            jobs = self.jobs(agent)
            self.assertEqual(len(jobs), len(routines_for(load_agent(agent))))
            for other in AGENTS:
                self.assertIn(f"(`{other}`)", soul, f"{agent} doesn't know {other}")
            self.assertTrue(all(j["state"] == "paused" for j in jobs))
            self.assertTrue(all(j["name"].startswith(f"[bot:{agent}] ") for j in jobs))
            for j in jobs:
                self.assertNotRegex(j["prompt"], r"\{\{[A-Z_]+\}\}")
            cfg = (self.home / "profiles" / agent / "config.yaml").read_text()
            self.assertIn("timezone: Europe/Berlin", cfg)
        skill = self.home / "profiles/coordinator/skills/autonomous-ai-agents/cornermen/SKILL.md"
        self.assertTrue(skill.exists())
        for f in self.ws.rglob("*"):
            if f.is_file():
                self.assertNotRegex(f.read_text(), r"\{\{[A-Z_]+\}\}", str(f))
        team_md = (self.ws / "shared" / "team.md").read_text()
        for agent in AGENTS:
            self.assertIn(f"`{agent}`", team_md)
            if agent != "coordinator":
                for f in ("summary.md", "log.md", "questions.md", "next-week.md"):
                    self.assertTrue((self.ws / agent / f).exists(), f"{agent}/{f}")
                self.assertTrue((self.ws / "shared" / "briefs" / f"{agent}.md").exists())
        self.assertEqual(json.loads((self.ws / "team.json").read_text())["agents"], AGENTS)

    def test_preset_team(self):
        self.install("--team", "minimal")
        self.assertEqual(json.loads((self.ws / "team.json").read_text())["agents"], ["coordinator", "fitness"])
        self.assertFalse((self.home / "profiles" / "builder").exists())
        self.assertNotIn("(`builder`)", self.soul("coordinator"))

    def test_add_catalog_agent_updates_every_persona(self):
        self.install()
        self.change("--add", "distributor")
        team = AGENTS + ["distributor"]
        for agent in team:
            self.assertIn("(`distributor`)", self.soul(agent), agent)
        self.assertTrue(all(j["state"] == "paused" for j in self.jobs("distributor")))
        self.assertIn("Distributor", (self.ws / "shared" / "team.md").read_text())
        self.assertTrue((self.ws / "distributor" / "content-calendar.md").exists())
        res = self.run_script("doctor.py", "--workspace", str(self.ws))
        self.assertIn("team of 6", res.stdout)

    def test_scaffold_custom_agent_then_add(self):
        name = "zz-finance-test"
        dest = REPO / "agents" / name
        self.addCleanup(lambda: __import__("shutil").rmtree(dest, ignore_errors=True))
        self.run_script("new-agent.py", name, "--title", "Finance", "--tagline", "budget and savings")
        spec = load_agent(name)
        self.assertEqual(spec["title"], "Finance")
        self.assertNotIn("__", (dest / "SOUL.md").read_text())
        self.install("--team", "minimal")
        self.change("--add", name)
        self.assertIn(f"(`{name}`)", self.soul("fitness"))
        self.assertTrue((self.ws / "shared" / "briefs" / f"{name}.md").exists())
        names = [j["name"] for j in self.jobs(name)]
        self.assertIn(f"[bot:{name}] Weekly check", names)
        self.assertIn(f"[bot:{name}] Friday planning input", names)
        bad = self.run_script("new-agent.py", "Bad Name", ok=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_remove_pauses_and_drops_from_roster(self):
        self.install()
        self.run_script("activate.py", "--workspace", str(self.ws))
        self.change("--remove", "social")
        self.assertNotIn("social", json.loads((self.ws / "team.json").read_text())["agents"])
        self.assertTrue(all(j["state"] == "paused" for j in self.jobs("social")))
        self.assertNotIn("(`social`)", self.soul("coordinator"))
        self.assertTrue((self.ws / "social" / "summary.md").exists())
        bad = self.run_script("install.py", "--workspace", str(self.ws), "--remove", "coordinator", ok=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_unknown_agent(self):
        res = self.run_script("install.py", "--timezone", "UTC", "--workspace", str(self.ws), "--add", "nope", ok=False)
        self.assertIn("new-agent.py", res.stderr)

    def test_reinstall_is_idempotent_and_keeps_user_edits(self):
        self.install()
        about = self.ws / "shared" / "about-me.md"
        about.write_text("# About me\n- Name: Alex\n")
        before = {a: len(self.jobs(a)) for a in AGENTS}
        self.install()
        self.assertEqual(about.read_text(), "# About me\n- Name: Alex\n")
        self.assertEqual(before, {a: len(self.jobs(a)) for a in AGENTS})
        creates = [c for c in (self.home / "calls.log").read_text().splitlines() if '"profile", "create"' in c]
        self.assertEqual(len(creates), len(AGENTS))

    def test_activate_skips_kickoffs_and_pause_reverts(self):
        self.install()
        self.run_script("activate.py", "--workspace", str(self.ws))
        for agent in AGENTS:
            for j in self.jobs(agent):
                expected = "paused" if j["name"].endswith("Onboarding kickoff") else "scheduled"
                self.assertEqual(j["state"], expected, j["name"])
        self.run_script("activate.py", "--workspace", str(self.ws), "--pause")
        self.assertTrue(all(j["state"] == "paused" for a in AGENTS for j in self.jobs(a)))

    def test_fake_cli_rejects_flags_real_hermes_lacks(self):
        # Guards the contract: the fake mirrors Hermes v0.21's flags, so a typo'd or invented flag fails.
        shim = self.env["HERMES_BIN"]
        bad = subprocess.run([shim, "-p", "x", "cron", "create", "0 9 * * 1", "hi", "--start-paused"],
                             env=self.env, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        good = subprocess.run([shim, "-p", "x", "cron", "create", "0 9 * * 1", "hi", "--name", "n",
                               "--paused", "--paused-reason", "r"], env=self.env, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(self.jobs("x")[0]["paused_reason"], "r")

    def test_doctor(self):
        res = self.run_script("doctor.py", "--workspace", str(self.ws), ok=False)
        self.assertNotEqual(res.returncode, 0)
        self.install()
        res = self.run_script("doctor.py", "--workspace", str(self.ws))
        self.assertIn("All good.", res.stdout)

    def test_doctor_flags_stale_calendar_token(self):
        # A stale calendar token should be flagged, not silently ignored.
        self.install()
        tok = self.home / "profiles" / "coordinator" / "google_token.json"
        tok.write_text('{"token": "x"}')
        res = self.run_script("doctor.py", "--workspace", str(self.ws))
        self.assertIn("calendar token refreshed", res.stdout)
        old = time.time() - 9 * 86400
        os.utime(tok, (old, old))
        res = self.run_script("doctor.py", "--workspace", str(self.ws))
        self.assertIn("probably expired", res.stdout)
        self.assertNotIn('"x"', res.stdout)

    def test_dry_run_changes_nothing(self):
        res = self.run_script("install.py", "--timezone", "Asia/Tokyo", "--workspace", str(self.ws), "--dry-run")
        self.assertIn("dry run", res.stdout)
        self.assertFalse(self.ws.exists())
        self.assertFalse((self.home / "profiles").exists())

    def test_bad_timezone(self):
        res = self.run_script("install.py", "--timezone", "Mars/Olympus", "--workspace", str(self.ws), ok=False)
        self.assertIn("unknown timezone", res.stderr)


class TemplateLintTest(unittest.TestCase):
    """House style for everything the agents read."""

    def files(self):
        for f in REPO.rglob("*"):
            if f.suffix in {".md", ".json"} and ".git" not in f.parts:
                yield f

    def test_no_dashes_that_read_as_ai(self):
        for f in self.files():
            self.assertNotRegex(f.read_text(), "[\u2013\u2014]", f"em/en dash in {f.relative_to(REPO)}")

    def test_routines_well_formed(self):
        for agent in catalog():
            jobs = routines_for(load_agent(agent))
            slugs = [j["slug"] for j in jobs]
            self.assertEqual(len(slugs), len(set(slugs)), agent)
            for j in jobs:
                self.assertIn(j["deliver"], {"telegram", "local", "origin"})
                self.assertRegex(j["schedule"], r"^[\d*,/ -]+$")
                if j["deliver"] == "local":
                    self.assertTrue("[SILENT]" in j["prompt"], f"{agent}/{j['slug']} is local but not silent")
            self.assertEqual(sum(j.get("kind") == "kickoff" for j in jobs), 1, agent)


class NewAgentTest(unittest.TestCase):
    def test_quotes_in_tagline_keep_valid_json(self):
        name = "zz-quote-test"
        dest = REPO / "agents" / name
        try:
            res = subprocess.run([sys.executable, str(REPO / "scripts" / "new-agent.py"), name,
                                  "--tagline", 'budget "and" savings'], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            data = json.loads((dest / "agent.json").read_text())
            self.assertEqual(data["tagline"], 'budget "and" savings')
        finally:
            import shutil
            shutil.rmtree(dest, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
