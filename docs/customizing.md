# Customizing

## Pick a team
`python3 scripts/install.py --list` shows the presets in `teams/` and every specialist in `agents/`.
- `starter`: coordinator, vision, fitness, builder, social (the default)
- `minimal`: coordinator and fitness. Grow from there.
- `creator`: coordinator, vision, builder, distributor

A preset only matters for the first install. After that, change the team with `--add` and `--remove`.

## Add your own specialist
```bash
python3 scripts/new-agent.py finance --title Finance --tagline "budget, savings, investing"
```
This copies `agents/_template/` to `agents/finance/`. Edit three files:
- `SOUL.md`: role, owned files, 3 to 5 behavior rules that make it good at its job, style. The installer appends the shared rules and roster.
- `brief.md`: copied to `shared/briefs/finance.md`; the coordinator fills it in from what you tell it.
- `agent.json`: title, tagline, message budget, question day and routines. Silent routines deliver `local` and end in `[SILENT]`. Set `"preamble": false` on a routine that shouldn't start with the standard preamble.

Area files you want created go in `agents/finance/files/`. Then:
```bash
python3 scripts/install.py --add finance
```
You still create its messaging bot (one token per profile). The coordinator runs its kickoff and asks before switching its routines on.

Prefer folding a role into an existing specialist until it has real work. Marketing lives inside Builder for that reason; add Distributor once there's a steady flow of things to share.

## Drop a specialist
`python3 scripts/install.py --remove social` pauses its routines and removes it from the roster and every persona. The profile and its files stay, so `--add social` brings it back.

## Schedule
Routines are cron expressions in **your** timezone, in each specialist's `agent.json`.
- **Before installing:** edit the JSON.
- **After installing:** `hermes -p <agent> cron list`, then `hermes -p <agent> cron edit <id> --schedule "0 8 * * 6"`. Re-running the installer won't duplicate or overwrite an edited routine.

## Quieter or louder
Budgets live in each `agent.json` (shown in `shared/team.md`); quiet hours in `shared/system.md`. The easiest way to change them is to tell the coordinator ("Social can suggest twice a week", "no messages before 09:00"). It records the decision.

## Different chat platform
Change `deliver` from `telegram` to any target your Hermes gateway supports before installing, or edit the jobs afterwards.

## Your voice
Whoever writes public content (Builder, or Distributor if it's on the team) drafts in your voice. Drop writing you're happy to share into its `voice/samples/`: published posts, essays, plus a few pieces by people you'd like to sound like. Agents only use what you put there; they never mine your chats or voice notes for style. It derives `voice/guide.md`, checks every draft against it and turns your edits into new rules.

## Calendar
Optional. Use Hermes' `google-workspace` skill with a calendar-only scope in the coordinator profile, then symlink the token into the other profiles (the coordinator skill has the exact steps). Write the read command into the Integrations section of `shared/system.md`. Specialists read the calendar freely, and only the coordinator creates events, after your yes.

## Rename your fork
`python3 scripts/rename.py "My Team" --dry-run` shows every file it would touch; drop `--dry-run` to apply. It sets the display name (README title, LICENSE, architecture image source) and the slug everywhere else, and moves the coordinator skill folder. Re-render the listed image and rename your GitHub repo yourself.
