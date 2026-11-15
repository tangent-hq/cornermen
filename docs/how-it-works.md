# How it works

## Recommended deployment

Run Hermes and Cornermen on an always-on remote server. Your laptop and phone are clients; the server holds the workspace and runs scheduled routines.

1. **Server:** install [Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation), configure a model, then follow the [Cornermen setup](../README.md#set-it-up). Run `hermes serve` for the desktop backend. Keep it bound to the default `127.0.0.1` address.
2. **Laptop:** install [Hermes Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/desktop). In **Settings → Gateways**, add an SSH connection to the server. SSH tunnels the connection without opening the backend port to the internet. Desktop can start its backend for an SSH connection; keep the messaging gateway running independently for Telegram and scheduled work.
3. **Phone:** connect each specialist's Telegram bot to its Hermes profile on the server, then message it in Telegram. This uses the messaging gateway, not `hermes serve` alone. Set up a managed gateway service using the [Hermes gateway guide](https://hermes-agent.nousresearch.com/docs/user-guide/multi-profile-gateways) so it stays running after you disconnect.

Keep the workspace, model credentials and bot tokens on the server. Back up the workspace privately. Local-only use is possible, but the server setup is the intended way to use this template.

[Remote connection guide](https://hermes-agent.nousresearch.com/docs/user-guide/multi-connection-desktop)

## The pieces
- **Hermes profiles.** Each specialist is its own profile (the starter team: `coordinator`, `vision`, `fitness`, `builder`, `social`) with its own persona (`SOUL.md`), memory, skills, cron jobs and messaging bot. Profiles never share memory.
- **Agent definitions.** `agents/<name>/` holds the persona, the brief and `agent.json` (title, what it owns, message budget, question day, routines). Every specialist automatically also gets a Friday planning-input routine, a one-time onboarding kickoff and the standard files (`summary.md`, `log.md`, `questions.md`, `next-week.md`).
- **The workspace.** `~/cornermen/` is a plain folder. Every persona points at it, and every routine runs with it as the working directory.
- **The persona.** Each `SOUL.md` is a short, agent-specific part (role, owned files, behavior, style) plus an identical block of standing rules and the current roster (`core/rules.md`). The installer joins them and fills in your paths, timezone and team. It re-renders every persona when the team changes.
- **The roster.** `team.json` at the workspace root (machine-readable) and `shared/team.md` (table, budgets, question days, schedules) are regenerated on every install.
- **Routines.** Hermes cron jobs, defined per specialist in `agent.json`. Unless a routine opts out, every prompt starts with the same preamble (`core/preamble.txt`): read `shared/`, read your lines on the team board, follow the contact policy, log what you did, answer `[SILENT]` if nothing is worth saying.

## Rules that keep it sane
| Rule | Why |
|---|---|
| Only the coordinator writes `shared/` | One source of truth for goals and priorities. Several writers means several versions. |
| Agents write only their own folder | Every file has an owner, so mistakes are traceable and fixable. |
| `summary.md` stays under ~20 lines | Agents read each other's summaries constantly. Short summaries are cheap and current. |
| `log.md` is append-only, with dated headings | History is never rewritten, so the monthly audit can trust it. |
| Facts go in files, not memory | Other agents can't read your memory. Files are also what you can see and fix. |
| `[SILENT]` by default | The scheduler suppresses delivery, so a routine that has nothing to say costs you nothing. |
| Message budgets per agent | Stops the system from turning into a feed. The coordinator tunes them in the audit. |
| One open ask per agent, back off after 2 unanswered | Repeated unanswered check-ins are noise. Silence from the user is information. |
| The weekly plan is in force when sent | Waiting for a same-day reply would stall the week; approval gates only calendar writes. |
| **Approve?** before consequences | Public posts, money, sign-ups, contacting people and calendar writes always need your explicit yes. |

## The team board
`coordinator/inbox.md` is a single append-only file:

```
- 2026-03-13 [from: fitness] [to: coordinator] Trip Thu to Sun in the calendar. Switching to the no-equipment plan.
- 2026-03-13 [from: vision] [to: builder] Direction is leaning toward building in public. Prefer projects with a public artifact.
- 2026-03-13 [re: 2026-03-13 from vision] [from: builder] Noted. The next repo ships public with a write-up.
- 2026-03-14 [from: coordinator] [to: all] Plan approved. Builder: Sat 10:30. Fitness: Mon, Wed, Fri 19:00. [done]
```

Agents read lines addressed to them (or `all`) at the start of every scheduled run. The coordinator marks lines `[done]` or `[rejected: reason]` during the Saturday review.

## The weekly cycle
1. **Friday 20:00.** Each area agent refreshes `summary.md` and overwrites `next-week.md` with its time asks (what, how long, when, fixed or flexible, must/should/nice), up to 2 decisions it needs from you, and anything the coordinator should know.
2. **Saturday 09:00.** The coordinator reads every summary, every `next-week.md`, the board and your calendar. It settles conflicts, updates `priorities.md`, writes one plan to `coordinator/plans/<date>.md` and sends it to you with "Approve?".
3. **Your reply** (often hours later, in the coordinator's chat). It applies your changes, creates the calendar events only after your yes, and posts each agent its agreed slots on the board.
4. **First Saturday of the month.** System audit: what each agent sent, what you acted on, what you ignored. Routines that don't pay off get cut, and every change goes in `decisions.md`.

## Onboarding
The installer creates every routine paused. The coordinator's first job is intake: one long brain dump from you, saved verbatim in the private, gitignored `.local/<date>-context-dump.md` and distilled into `shared/` and the specialists' briefs. Then it runs one agent's kickoff per day. Each agent fills its own files from the shared context, writes a ranked `questions.md`, and asks you only its most important question. Once the shared files are real, the coordinator asks to switch the routines on.
