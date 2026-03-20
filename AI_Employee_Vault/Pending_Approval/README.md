# /Pending_Approval — Awaiting Your Review

Claude writes approval request files here for sensitive actions (sending emails, payments, posting to social media).

## How to Approve
Move the file to an `/Approved/` folder (you can create it here). The orchestrator detects the move and triggers the action.

## How to Reject
Move the file to a `/Rejected/` folder (or simply delete it). Claude will log the rejection.

## File Format
```markdown
---
type: approval_request
action: <send_email | payment | social_post | other>
created: YYYY-MM-DDTHH:MM:SSZ
expires: YYYY-MM-DDTHH:MM:SSZ
status: pending
---

## Action Details
<What Claude wants to do>

## To Approve
Move this file to /Approved/

## To Reject
Move this file to /Rejected/
```
