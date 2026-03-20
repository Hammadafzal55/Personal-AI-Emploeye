---
type: approval_request
action: post_linkedin
post_type: behind_scenes
created: 2026-03-16T13:00:00Z
expires: 2026-03-18T13:00:00Z
status: done
estimated_reach: organic
---

## Post Content

I built myself an AI employee over the weekend. Here's what it can already do.

Most people think AI assistants = chatbots.

What I built is different.

It reads my emails, drafts replies, processes my task queue, and routes sensitive actions to me for approval — all autonomously, while I focus on real work.

I'm calling it a Digital FTE (Full-Time Equivalent). Built with Claude Code and Obsidian in under 48 hours as part of a personal hackathon.

Here's how it works:

A filesystem watcher detects new files dropped into a vault folder. An orchestrator wakes up Claude Code every 60 seconds. Claude reads its "Company Handbook" (its rules of engagement), processes each task, and writes action plans.

For anything sensitive — sending emails, posting on social, making payments — it routes to a /Pending_Approval folder and waits for my sign-off.

No rogue actions. No hallucinations acted upon. Full audit trail in markdown.

The best part? It runs entirely locally. No cloud required. Obsidian is the dashboard.

I'm building this into an open template for entrepreneurs, freelancers, and developers who want to automate their operations without giving up control.

Interested in early access or want to build your own? Drop a comment or send me a DM.

## Hashtags
#AIAutomation #ClaudeAI #BuildInPublic #AIEngineering #PersonalProductivity

## Rationale
The Personal AI Employee (Hackathon 0) project is actively running at Silver tier. This post serves the Q1 2026 goal of increasing LinkedIn visibility and generating leads (target: 5+ new leads/month). The "Behind the Scenes" format performs well for technical audiences and directly speaks to the target audience: entrepreneurs wanting AI automation + developers/students entering the field. No confidential client data is included.

## To Approve
Move this file to `/Pending_Approval/Approved/`
The orchestrator will call `actions/post_linkedin.py` to post automatically.

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text above before approving.

## Resolution
- **Date:** 2026-03-16
- **Action taken:** Approval request routed to `/Pending_Approval/LINKEDIN_PersonalAIEmployee_2026-03-16.md`. Per Company_Handbook §5, social media posting requires human sign-off. Post content (Behind the Scenes — Personal AI Employee) preserved. Awaiting human approval before `post_linkedin.py` is called.
- **Scheduled for:** 2026-03-16
- **Status:** ✅ Processed — pending human approval