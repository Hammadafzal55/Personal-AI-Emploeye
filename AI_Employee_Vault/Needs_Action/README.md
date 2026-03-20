# /Needs_Action — Claude's Work Queue

This folder is Claude's inbox. Every `.md` file here is a task for Claude to process.

## File Naming Convention
- `EMAIL_<id>.md` — From Gmail Watcher
- `WHATSAPP_<contact>_<date>.md` — From WhatsApp Watcher
- `FILE_<original_name>.md` — From Filesystem Watcher (Inbox drop)
- `TASK_<description>_<date>.md` — Manually created tasks

## What Claude Does
1. Reads each file here.
2. Decides the right action based on `Company_Handbook.md`.
3. Creates a `Plan_*.md` in `/Plans/` if multi-step.
4. Either acts immediately (safe actions) or writes to `/Pending_Approval/`.
5. Moves the file to `/Done/` when resolved.
