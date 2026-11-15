# Cornermen workspace

The shared brain of a specialist agent team. Every agent reads `shared/`; each one writes only in its own folder.
How the system works: `shared/system.md`.

| Folder | Owner | What lives here |
|---|---|---|
| `shared/` | coordinator (only editor) | who the user is, goals, priorities, preferences, system rules, `team.md`, agent briefs |
| `coordinator/` | coordinator | team board (`inbox.md`), decisions, weekly reviews, plans |
| `<specialist>/` | that specialist | its summary, log, questions, planning input and area files |

`team.json` (machine-readable roster) and `shared/team.md` are written by the installer.


Conventions: `summary.md` stays under ~20 lines; `log.md` is append-only with `## YYYY-MM-DD` headings; files marked TEMPLATE haven't been filled in yet.
