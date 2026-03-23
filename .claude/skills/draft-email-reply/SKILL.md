# Skill: draft-email-reply

Draft a professional reply to an incoming email and route it through the
Human-in-the-Loop approval workflow before sending.

## Trigger
- An `EMAIL_*.md` file exists in `AI_Employee_Vault/Needs_Action/`
- Called by the `process-inbox-tasks` skill when the task type is `email`

## Steps

### 1. Read context
- Read `AI_Employee_Vault/Company_Handbook.md` — tone, rules, sign-off name
- Read `AI_Employee_Vault/Business_Goals.md` — business context for replies
- Read the `EMAIL_*.md` file — extract From, Subject, thread_id, internet_message_id, Body

### 2. Decide action
- If the email is **promotional / notification-only** (no reply needed): move to Done with `status: done`, no draft needed.
- If the email is **from a new unknown contact**: flag for approval with a note before drafting.
- If the email **requires a reply**: proceed to Step 3.

### 3. Draft the reply body
Write the reply body to `AI_Employee_Vault/Plans/DRAFT_reply_<message_id>_<date>.md`.

**CRITICAL: Write ONLY the plain email body text. Nothing else.**
- No YAML frontmatter
- No markdown headers (no `##`, no `---`)
- No `*Drafted by AI Employee*` footer or any meta-text
- No `## Draft Reply` heading
- Just the email body exactly as it should be sent — greeting, content, sign-off

Example of correct output:
```
Hi Afzal,

Thank you for reaching out. [reply content here]

Best regards,
Hammad Afzal
```

### 4. Write the approval request
Write `AI_Employee_Vault/Pending_Approval/EMAIL_SEND_<message_id>_<date>.md`:

**CRITICAL: The frontmatter fields below are machine-read by the gmail MCP server.
Every field is required. Missing `to:` or `body_file:` will cause the send to silently fail.**

```markdown
---
type: approval_request
action: send_email
to: <sender email address>
subject: Re: <original subject>
thread_id: <thread_id from EMAIL_*.md>
in_reply_to: <internet_message_id from EMAIL_*.md>
body_file: AI_Employee_Vault/Plans/DRAFT_reply_<message_id>_<date>.md
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
new_contact: false
---

## Email to Send

**To:** <sender email>
**Subject:** Re: <original subject>

<paste the draft body here for human review>

## To Approve
Move this file to `/Pending_Approval/Approved/`

## To Reject
Move this file to `/Pending_Approval/Rejected/`
```

### 5. Move source file to Done
After creating the approval request, **immediately** move the original `EMAIL_*.md`
from `/Needs_Action/` to `/Done/` with:
- `status: pending_approval`
- A `## Resolution` section: `Approval request created: EMAIL_SEND_<id>.md`

Do NOT leave it in `/Needs_Action/` — it will be re-processed on the next cycle.

### 6. Update Dashboard + Log
- Append to `AI_Employee_Vault/Logs/<today>.md`
- Update `AI_Employee_Vault/Dashboard.md` — increment Approvals Pending, add Recent Activity row

## Rules
- Never fabricate facts about the business or commitments not in Company_Handbook.md
- Keep replies concise — 3–5 sentences unless the email warrants more
- Always use the sign-off name from Company_Handbook.md Section 10
- Never send to a new contact without explicit approval note in the request
- The `body_file` path must be relative to the project root, not absolute
