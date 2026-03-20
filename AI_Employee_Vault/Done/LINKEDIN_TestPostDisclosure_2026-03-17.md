---
type: approval_request
action: post_linkedin
post_type: disclosure
created: 2026-03-17T14:00:00+05:00
status: done
estimated_reach: organic
---

## Post Content

Transparency post — the last few posts on my profile were written and published by my AI employee, not manually by me.

This is part of Hackathon 0 — the challenge: build an autonomous AI-powered Digital FTE (Full-Time Employee) using Claude Code.

My implementation hit Silver tier this week:

- 📬 Gmail Watcher — reads incoming emails, creates task files automatically
- ✍️ Draft Engine — writes email replies and LinkedIn posts in my brand voice
- ✅ Human-in-the-Loop — nothing gets sent without my approval
- 🗂️ Task Queue — manages work from a local markdown vault using Obsidian

The posts about AI automation, junior dev career advice, and the project journey? My AI drafted them, I approved them, and it posted them automatically via Playwright.

Sharing this because transparency matters — and honestly, watching it work is still kind of wild.

The whole stack is Python + Claude Code + plain markdown files. No cloud, no SaaS, runs entirely on my laptop.

If you're curious about what's possible with AI tooling in 2026 — this is it. Drop a comment or DM me.

#AIAutomation #BuildInPublic #ClaudeAI #HackathonProject #AIEngineering #StudentProject

## Rationale
Corrects the record — these were test posts from a course hackathon, not a personal side project. Transparency builds trust and the "course hackathon" framing makes it relatable to students and developers in the audience.

## To Approve
Move this file to `/Pending_Approval/Approved/`
The orchestrator will call `actions/post_linkedin.py` to post automatically.

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text above before approving.
