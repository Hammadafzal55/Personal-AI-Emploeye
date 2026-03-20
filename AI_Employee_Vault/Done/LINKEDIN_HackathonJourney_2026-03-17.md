---
type: approval_request
action: post_linkedin
post_type: behind_scenes
created: 2026-03-17T09:00:00+05:00
expires: 2026-03-19T09:00:00+05:00
status: done
estimated_reach: organic
---

## Post Content

I built a Personal AI Employee in a weekend — and it just read my emails, drafted replies, and scheduled LinkedIn posts without me touching a single button.

Here's how it works:

**The core idea:** Instead of using AI as a chatbot, I gave it a job.

It has a "vault" — a folder of markdown files acting as its inbox, task queue, and memory. Every morning it wakes up, reads its company handbook (the rules I wrote), checks what needs doing, and gets to work.

This week it hit Silver tier:
- 📧 Gmail Watcher: scans unread emails, creates task files automatically
- ✍️ Draft Engine: writes replies and LinkedIn posts following my brand voice
- 🔒 Human-in-the-Loop: nothing gets sent without a file moved to /Approved/
- 🗓️ Scheduler: runs daily briefings at 8AM without me asking

The stack is surprisingly simple: Claude Code + Python watchers + plain markdown files.

No fancy infra. No cloud servers. Runs entirely on my laptop.

If you're a developer, student, or entrepreneur curious about AI automation — this is proof you don't need a team or a big budget to build something powerful.

What would YOU automate first if you had a digital employee? Drop it in the comments.

## Hashtags
#AIEngineering #Automation #ClaudeAI #BuildInPublic #PersonalAI #SoftwareDevelopment #HackathonProject #CareerInTech

## Rationale
The Personal AI Employee (Hackathon 0) is the primary active project. Sharing the Silver tier milestone serves multiple business goals simultaneously: showcases AI engineering skills to potential clients, builds audience with entrepreneurs and junior devs (core target audience), and drives engagement via a question CTA. Aligns with the "hackathon journey" and "project showcase" content pillars from Company_Handbook.md Section 10.

## To Approve
Move this file to `/Pending_Approval/Approved/`
The orchestrator will call `actions/post_linkedin.py` to post automatically.

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text above before approving.
