---
name: cornermen
description: "Use when running or changing the Cornermen specialist team. Intake, onboarding, adding agents, going live, audits."
version: 1.0.0
author: cornermen
license: MIT
metadata:
  hermes:
    tags: [multi-agent, profiles, personal-assistant, cron, coordinator]
    related_skills: [hermes-agent, google-workspace]
---

# Cornermen (coordinator playbook)

A coordinator plus a team of specialist Hermes profiles (current roster: `shared/team.md`) share one plain folder, `{{WORKSPACE}}/`. Each specialist fights for one area of the user's life; you judge between them. The coordinator owns `shared/` and keeps the system useful. The template repo lives at `{{REPO}}`.

## Design rules (never break these)
- One profile per agent. Two agents on one profile cross-write memory.
- Shared context lives in files under `shared/`, referenced from each SOUL.md. Never copy it into agent memory: copies drift and memory is size-capped.
- Single writer: only the coordinator edits `shared/`. Everyone else proposes on the team board (`coordinator/inbox.md`).
- Per-agent briefs live in `shared/briefs/<agent>.md`, so SOULs stay short and the single-writer rule holds.
- Silent by default. Every routine either has something worth the user's attention or answers `[SILENT]`. Housekeeping jobs deliver `local`.
- Each agent asks its own questions in its own chat. Don't relay, except as a stopgap while an agent has no messaging bot yet.
- Don't throttle agents because of calendar deadlines. The user decides their own load; the calendar is scheduling context, not a priority signal.

## Intake (first contact, or a big new briefing)
1. Read everything first: `shared/*`, every `*/summary.md`, `hermes profile list`, each agent's `hermes -p <agent> cron list`, and the calendar for the next two weeks if connected.
2. Ask for one long brain dump (voice note ideal). Save the raw text verbatim to `.local/<date>-context-dump.md` (gitignored, so a normal git backup skips it; keep any other backup or sync private too) so you can reread the user's own words later; briefs are summaries and lose nuance. Everything you write into `shared/` follows the privacy principle in `system.md`.
3. Rewrite `shared/about-me.md`, `goals.md`, `preferences.md`. Keep `(confirm)` on anything inferred. Tentative targets are not targets: write them as "idea, not set".
4. Fill every `shared/briefs/<agent>.md` from the dump (for example a builder's radar sources and repo rule). If the dump names an area no specialist covers, propose adding one (see Changing the team).
5. Set `shared/priorities.md`: top 3 for this week, time split, not-doing list.
6. Remove the TEMPLATE banner from each file you filled.
7. Log it in `coordinator/weekly-review.md` and post a kickoff line to `all` on the board.

## Staggered onboarding
- One agent's kickoff per day, never all at once: `hermes -p <agent> cron list --all` to find its `Onboarding kickoff` job, then `hermes -p <agent> cron run <id>`.
- If the user says they have time now, run the remaining kickoffs immediately.
- Before telling the user a message went out, check `~/.hermes/profiles/<agent>/cron/output/<job_id>/` for the response.
- Order that works: quick-win areas first (e.g. training), then project and relationship areas, and direction last, when trust exists.

## Going live
1. Confirm with the user: "Approve? I'll switch on the weekly routines: <one line per agent>."
2. After the yes: `python3 {{REPO}}/scripts/activate.py` (resumes every `[bot:*]` routine except kickoffs). Or per job: `hermes -p <agent> cron resume <id>`.
3. Record the decision in `decisions.md`, update the Autonomy section of `system.md` if you changed anything, and post a line to `all` on the board.
4. If the user launches mid-week, run each agent's `Friday planning input` once so the first Saturday plan has material.

## Messaging setup (user-only steps)
- One messaging bot token per profile. Two profiles on one token collide. Easiest: Hermes desktop, Messaging, Telegram, create via QR, once per profile.
- Never accept a token pasted in chat. Point the user to the setup flow.
- After cloning a profile, copy the non-secret allowlist lines (e.g. `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_HOME_CHANNEL`) from a sibling profile's `.env` if the new bot ignores the user.

## Timezone pitfall
Cron runs in the host timezone unless the profile sets one. The installer runs `hermes -p <agent> config set timezone <TZ>` for every profile. A multiplexed gateway caches timezones per process: restart the whole gateway afterwards (`hermes gateway restart` from the default profile), then check that `Next run` in `cron list` shows the local offset.

## Calendar (optional)
- Before the first authorization, set the Google Cloud OAuth app's publishing status to **In production**. Apps left in "Testing" get refresh tokens that expire after 7 days, and because every profile shares the token, the whole team loses the calendar at once. `scripts/doctor.py` warns when the token is stale.
- Use the `google-workspace` skill's OAuth flow with a calendar-only scope. Authorize once in the coordinator profile, then symlink (not copy) `google_token.json` and `google_client_secret.json` into every other profile so token refreshes stay consistent.
- Write the exact read command into the Integrations section of `shared/system.md`. Every routine looks there.
- Agents read freely. Creating, moving or deleting events requires the user's explicit yes, in chat, never inside a cron run.
- Writing events: look for an existing matching event first, store every created event ID in the plan file, use timed events (not all-day) unless asked, and never surprise people on a shared calendar.

## Changing the team
Add a specialist when the user names an area that nobody owns and it has recurring work. Drop or merge one when it has had nothing useful to say for a month.
1. Propose it: "Approve? I'll add a <name> specialist that owns <area>, with <routines>, budget <budget>." Record the yes in `decisions.md`.
2. If the repo ships a matching agent (`python3 {{REPO}}/scripts/install.py --list`), use it. Otherwise scaffold one: `python3 {{REPO}}/scripts/new-agent.py <name> --title "<Title>" --tagline "<area>"`, then edit `agents/<name>/SOUL.md` (role, owned files, 3 to 5 behavior rules, style), `brief.md` and `agent.json` (budget, question day, routines; silent routines deliver `local` and end in `[SILENT]`).
3. Install it: `python3 {{REPO}}/scripts/install.py --add <name>`. This creates the profile, its folder and brief, regenerates `shared/team.md`, re-renders every persona with the new roster, and creates its routines paused.
4. The user creates its messaging bot (one token per profile). Run its kickoff (`hermes -p <name> cron list --all`, then `cron run <id>`), and after the user's yes: `python3 {{REPO}}/scripts/activate.py --agent <name>`.
5. Dropping: `python3 {{REPO}}/scripts/install.py --remove <name>` pauses its routines and removes it from the roster; the profile and files stay, so it can come back.
6. Prefer folding a role into an existing specialist until it has real work (e.g. marketing inside Builder until there's a steady flow of shipped things). Record the call and its revisit trigger in `decisions.md`.

## Monthly audit checklist
- Per agent: messages sent, approvals asked, silent runs, failures: `python3 {{REPO}}/scripts/stats.py --days 31` (add `--json` to keep the numbers). Then judge which messages the user acted on and which were ignored (chat replies, logs).
- Routines with zero useful output in a month: cut or rewrite.
- Budgets: is anyone over? Is the user complaining about noise or about silence?
- Summaries: still under ~20 lines and current?
- Record every change in `decisions.md`; report in 3 to 5 lines.

## Reporting to the user
When asked "what's running?", list running, done and scheduled separately, and say plainly what is not verified yet.
