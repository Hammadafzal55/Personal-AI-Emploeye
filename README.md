# Personal AI Employee — Silver Tier

> *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

A **Digital FTE (Full-Time Equivalent)** built with Claude Code + Obsidian.
**Silver Tier** implementation of the [Personal AI Employee Hackathon 0](./Personal%20AI%20Employee%20Hackathon%200_%20Building%20Autonomous%20FTEs%20in%202026.md).

---

## Tier Checklist

### ✅ Bronze (Foundation)
| Requirement | Status | Implementation |
|---|---|---|
| Obsidian vault with `Dashboard.md` + `Company_Handbook.md` | ✅ | `AI_Employee_Vault/` |
| Basic folder structure (`/Inbox`, `/Needs_Action`, `/Done`, `/Plans`, `/Logs`, `/Pending_Approval`) | ✅ | Auto-created by orchestrator |
| One working Watcher script | ✅ | `watchers/filesystem_watcher.py` |
| Claude Code reads/writes the vault | ✅ | `orchestrator.py` poll loop |
| All AI functionality as Agent Skills | ✅ | `.claude/skills/` — 5 skills |

### ✅ Silver (Functional Assistant)
| Requirement | Status | Implementation |
|---|---|---|
| All Bronze requirements | ✅ | See above |
| Two or more Watcher scripts | ✅ | `filesystem_watcher.py` + `gmail_watcher.py` |
| Auto-post on LinkedIn to generate sales | ✅ | `actions/post_linkedin.py` + `draft-linkedin-post` skill |
| Claude reasoning loop creating `Plan.md` files | ✅ | Claude writes `Plans/Plan_*.md` on multi-step tasks |
| One working MCP server for external actions | ✅ | Playwright MCP (`browsing-with-playwright` skill) — LinkedIn browser automation |
| Human-in-the-loop approval workflow | ✅ | `/Pending_Approval/` → terminal A/R prompt → `/Approved/` → action |
| Basic scheduling (cron / Task Scheduler) | ✅ | `schedule` library inside `orchestrator.py` |
| All AI functionality as Agent Skills | ✅ | 5 skills: `process-inbox-tasks`, `draft-email-reply`, `draft-linkedin-post`, `process-approvals`, `weekly-ceo-briefing` |

---

## Architecture

```
╔══════════════════════════════════════════════════════════════╗
║              PERCEPTION LAYER (Watchers)                     ║
║                                                              ║
║  📁 filesystem_watcher.py   📧 gmail_watcher.py             ║
║  Watches /Inbox for files   Polls Gmail History API          ║
║         ↓                           ↓                        ║
║  FILE_*.md → /Needs_Action  EMAIL_*.md → /Needs_Action       ║
╚══════════════════════════════════════════════════════════════╝
                        ↓
╔══════════════════════════════════════════════════════════════╗
║              REASONING LAYER (Claude Code)                   ║
║                                                              ║
║  orchestrator.py polls /Needs_Action every 120s             ║
║         ↓                                                    ║
║  Claude reads Company_Handbook.md → reasons → acts           ║
║  Safe tasks  → /Done (immediately)                           ║
║  Multi-step  → Plan_*.md in /Plans + then executes           ║
║  Sensitive   → writes to /Pending_Approval (HITL gate)       ║
╚══════════════════════════════════════════════════════════════╝
                        ↓
╔══════════════════════════════════════════════════════════════╗
║              ACTION LAYER (MCP + Scripts)                    ║
║                                                              ║
║  [Human reviews in terminal]                                 ║
║  A → /Approved/ → orchestrator dispatches:                   ║
║    📧 send_email.py   — Gmail API (OAuth2)                   ║
║    🔗 post_linkedin.py — Playwright MCP server               ║
║         ↓                                                     ║
║  Result logged → /Logs/YYYY-MM-DD.md                         ║
║  Dashboard.md updated                                        ║
╚══════════════════════════════════════════════════════════════╝
```

### Scheduler (time-based jobs)
| Job | Time | Skill |
|---|---|---|
| Daily briefing | 08:00 every day | writes `Briefings/DAILY_*.md` |
| LinkedIn post draft | 09:00 every day | `draft-linkedin-post` |
| Weekly CEO briefing | Monday 07:00 | `weekly-ceo-briefing` |
| Vault cleanup | Sunday 23:00 | removes stale promo/test files |

---

## Agent Skills

All AI reasoning is encapsulated as Claude Code Agent Skills (`.claude/skills/`):

| Skill | Trigger | Output |
|---|---|---|
| `process-inbox-tasks` | Files in `/Needs_Action` | Processes tasks, drafts replies, creates plans |
| `draft-email-reply` | `EMAIL_*.md` in Needs_Action | Plain-text reply → `/Pending_Approval/EMAIL_SEND_*.md` |
| `draft-linkedin-post` | Scheduler 09:00 / manual | Post → `/Pending_Approval/LINKEDIN_*.md` |
| `process-approvals` | Files in `/Approved/` | Dispatches send_email or post_linkedin |
| `weekly-ceo-briefing` | Monday 07:00 / manual | `Briefings/Monday_*.md` — full week audit |

---

## Vault Structure

```
AI_Employee_Vault/
├── Dashboard.md              ← Real-time status (Claude updates after every run)
├── Company_Handbook.md       ← AI rules of engagement (YOU define this)
├── Business_Goals.md         ← Revenue targets & active projects
├── Inbox/                    ← Drop files here to trigger the AI
├── Needs_Action/             ← Claude's work queue (auto-cleared after processing)
├── Plans/                    ← Multi-step Plan_*.md + DRAFT_reply_*.md files
├── Done/                     ← Completed task archive (EMAIL_SEND_*, LINKEDIN_*)
├── Pending_Approval/         ← Sensitive actions waiting for A/R decision
│   ├── Approved/             ← Human moves here → action executes immediately
│   ├── Rejected/             ← Permanently rejected
│   └── Cancelled/            ← Rejected via terminal R command
├── Logs/                     ← Daily audit trail YYYY-MM-DD.md
└── Briefings/                ← DAILY_*.md + Monday CEO briefings
```

---

## Project Code Structure

```
Personal-AI-Emploeye/
├── orchestrator.py              ← Master process: watchers + Claude polling + HITL + scheduler
├── watchers/
│   ├── base_watcher.py          ← Abstract base class (BaseWatcher pattern)
│   ├── filesystem_watcher.py    ← Watches /Inbox — no external API needed
│   └── gmail_watcher.py         ← Polls Gmail History API for new emails only
├── actions/
│   ├── send_email.py            ← Gmail API: send reply in thread
│   └── post_linkedin.py         ← Playwright: types into LinkedIn Quill editor
├── setup/
│   └── gmail_oauth_setup.py     ← One-time OAuth2 flow for Gmail
├── .claude/
│   └── skills/
│       ├── process-inbox-tasks/ ← Core task processor
│       ├── draft-email-reply/   ← Email drafting + approval routing
│       ├── draft-linkedin-post/ ← LinkedIn post generator
│       ├── process-approvals/   ← Approval executor
│       ├── weekly-ceo-briefing/ ← Monday CEO audit
│       └── browsing-with-playwright/ ← Playwright MCP server (LinkedIn automation)
├── AI_Employee_Vault/           ← Obsidian vault (open this in Obsidian)
├── secrets/                     ← OAuth tokens, LinkedIn session (git-ignored)
├── CLAUDE.md                    ← Claude Code project config
├── .env.example                 ← Environment variable template
├── requirements.txt
└── Personal AI Employee Hackathon 0_...md  ← Original blueprint
```

---

## Setup

### 1. Prerequisites

- Python 3.13+
- Node.js v24+ LTS
- Claude Code: `npm install -g @anthropic/claude-code`
- Obsidian — open `AI_Employee_Vault/` as a vault

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DRY_RUN=false when ready
```

### 4. Gmail OAuth (one-time)

```bash
python setup/gmail_oauth_setup.py
# Saves token to secrets/gmail_token.json
```

### 5. LinkedIn session (one-time)

```bash
python actions/post_linkedin.py --setup
# Opens browser — log in manually — session saved to secrets/linkedin_session/
```

### 6. Customize the Handbook

Edit `AI_Employee_Vault/Company_Handbook.md` — fill in Section 10 (business name, industry, clients).

### 7. Run

```bash
python orchestrator.py
```

---

## Human-in-the-Loop (HITL) Workflow

Claude **never** sends emails or posts without your approval:

```
Claude writes /Pending_Approval/EMAIL_SEND_*.md
      ↓
Terminal shows: *** APPROVAL NEEDED — press Enter to review ***
      ↓
Decision [A/R] > A
      ↓
File moved to /Approved/ → send_email.py dispatched → email sent
```

Approval happens **before** any watcher or scheduler restarts — the orchestrator processes pending approvals synchronously at startup, then launches all background processes.

---

## Security

| Rule | Implementation |
|---|---|
| No credentials in vault | `.env` + `secrets/` (both git-ignored) |
| `DRY_RUN=true` default | Claude logs intent only — nothing sent externally |
| All actions logged | `/Logs/YYYY-MM-DD.md` with timestamps |
| HITL gate on sends | Every email/post requires explicit A before dispatching |

---

## Key Orchestrator Features

- **`_claude_lock`** — only one Claude subprocess runs at a time; concurrent calls are deferred
- **Startup approval handler** — existing approvals resolved before watchers start (clean terminal)
- **Post-Claude rescan** — immediately queues new approval files after Claude finishes (no race condition)
- **Watcher pipe logging** — FsWatcher and GmailWatcher output is buffered during approvals, flushed after
- **Startup catch-up** — runs missed scheduled jobs (briefing, LinkedIn draft) if orchestrator started late

---

## Next Tiers

| Tier | Key Additions |
|---|---|
| **Gold** | WhatsApp watcher, Odoo MCP server, Facebook/Instagram/Twitter integration, Ralph Wiggum stop-hook loop, full CEO business audit |
| **Platinum** | 24/7 cloud VM, cloud+local agent split, Vault sync via Git, Odoo on cloud with HITL payments |

---

## Hackathon Submission

- **Tier:** Silver ✅
- **Watchers:** Filesystem + Gmail (2 watchers)
- **MCP Server:** Playwright MCP (`browsing-with-playwright` skill) for LinkedIn browser automation
- **HITL:** Terminal A/R prompt → file-move pattern → action dispatch
- **Scheduler:** `schedule` library — daily briefing, LinkedIn post, weekly CEO briefing
- **Skills:** 5 Agent Skills covering all AI functionality
- **Demo flow:** Email arrives → Gmail watcher → Needs_Action → Claude drafts reply → Pending_Approval → user types A → email sent via Gmail API
