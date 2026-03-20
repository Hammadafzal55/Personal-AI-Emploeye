# Personal AI Employee — Bronze Tier

> *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

A **Digital FTE (Full-Time Equivalent)** built with Claude Code + Obsidian. This is the **Bronze Tier** implementation from the [Personal AI Employee Hackathon 0](./Personal%20AI%20Employee%20Hackathon%200_%20Building%20Autonomous%20FTEs%20in%202026.md).

---

## What Bronze Tier Delivers

| Feature | Status |
|---------|--------|
| Obsidian vault with `Dashboard.md` + `Company_Handbook.md` | ✅ |
| Basic folder structure (`/Inbox`, `/Needs_Action`, `/Done`, `/Plans`, `/Logs`, `/Pending_Approval`) | ✅ |
| Filesystem Watcher (detects files dropped into `/Inbox`) | ✅ |
| Claude Code reads/writes the vault | ✅ |
| `process-inbox-tasks` Agent Skill | ✅ |
| Orchestrator that ties everything together | ✅ |

---

## Architecture (Bronze)

```
You drop file → /Inbox
      ↓
Filesystem Watcher (filesystem_watcher.py)
      ↓
Creates FILE_*.md → /Needs_Action
      ↓
Orchestrator polls → triggers Claude Code
      ↓
Claude reads Company_Handbook.md + processes task
      ↓
Safe actions → /Done
Sensitive actions → /Pending_Approval (you approve)
      ↓
Dashboard.md + Logs updated
```

---

## Setup

### 1. Prerequisites

- Python 3.13+
- Node.js v24+ LTS
- Claude Code: `npm install -g @anthropic/claude-code`
- Obsidian (open `AI_Employee_Vault/` as a vault)

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your environment

```bash
cp .env.example .env
# Edit .env — set VAULT_PATH if needed, set DRY_RUN=false when ready
```

### 4. Customize the Handbook

Edit `AI_Employee_Vault/Company_Handbook.md` — fill in:
- Section 10: your business name, industry, clients
- Section 3: adjust financial thresholds
- Section 2: update communication rules

### 5. Set your goals

Edit `AI_Employee_Vault/Business_Goals.md` — fill in your revenue targets and active projects.

---

## Running the AI Employee

### Option A: Full orchestrator (recommended)

```bash
python orchestrator.py
```

This starts the filesystem watcher + polls for tasks every 2 minutes. Claude is triggered automatically when items appear in `/Needs_Action`.

> Set `DRY_RUN=false` in `.env` when you want Claude to actually process tasks.

### Option B: Manual one-shot run

```bash
claude --print "Read AI_Employee_Vault/Company_Handbook.md, then process all files in AI_Employee_Vault/Needs_Action/, create plans in Plans/, move done items to Done/, and update Dashboard.md."
```

### Option C: Drop a file and watch

1. Drop any `.md`, `.txt`, or `.csv` file into `AI_Employee_Vault/Inbox/`.
2. The Filesystem Watcher creates an action item in `AI_Employee_Vault/Needs_Action/`.
3. Run Claude manually (Option B) or let the orchestrator pick it up.

---

## Project Structure

```
Personal-AI-Emploeye/
├── AI_Employee_Vault/          ← Open this in Obsidian
│   ├── Dashboard.md            ← Real-time status (Claude updates this)
│   ├── Company_Handbook.md     ← AI rules of engagement (YOU define this)
│   ├── Business_Goals.md       ← Goals and metrics
│   ├── Inbox/                  ← Drop files here to trigger the AI
│   ├── Needs_Action/           ← Claude's work queue
│   ├── Plans/                  ← Multi-step action plans (written by Claude)
│   ├── Done/                   ← Completed task archive
│   ├── Pending_Approval/       ← Sensitive actions waiting for your OK
│   └── Logs/                   ← Daily audit trail
├── watchers/
│   ├── base_watcher.py         ← Abstract base class
│   └── filesystem_watcher.py   ← Watches /Inbox for dropped files
├── orchestrator.py             ← Master process: watcher + Claude trigger
├── .claude/
│   └── skills/
│       └── process-inbox-tasks/
│           └── SKILL.md        ← Agent Skill for Claude
├── CLAUDE.md                   ← Claude Code project configuration
├── requirements.txt
├── .env.example
└── Personal AI Employee Hackathon 0_...md  ← Original blueprint
```

---

## Human-in-the-Loop

Claude **never** sends emails, makes payments, or posts to social media without your approval.

When Claude needs approval, it writes a file to `/Pending_Approval/`. You:
1. Review the file in Obsidian.
2. Move it to `/Pending_Approval/Approved/` to proceed.
3. Move it to `/Pending_Approval/Rejected/` to cancel.

---

## Security

- Credentials live in `.env` only — **never in the vault**.
- `.env` is git-ignored.
- `DRY_RUN=true` by default — Claude logs intentions but doesn't act externally until you flip it.
- All actions are logged in `/Logs/YYYY-MM-DD.md`.

---

## Next Tiers

| Tier | Key Additions |
|------|--------------|
| **Silver** | Gmail Watcher, LinkedIn auto-posting, cron scheduling |
| **Gold** | Full MCP servers, WhatsApp, Business Audit + CEO Briefing |
| **Platinum** | 24/7 cloud deployment, cloud+local agent split |

---

## Hackathon Submission

- Tier: **Bronze**
- Credentials handling: `.env` file + `DRY_RUN` flag (no real credentials committed)
- Demo: Drop a file in `/Inbox` → watcher fires → Claude processes → `/Done`
