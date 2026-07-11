---
name: process-approvals
description: |
  Process files that have been moved to /Pending_Approval/Approved/ by the human.
  Reads each approved file, determines the action type, and executes the appropriate
  action (MCP tool for send_email/post_facebook/post_instagram, Python script for post_linkedin).
  Logs results and moves files to /Done/.
  Use when: orchestrator detects new files in /Pending_Approval/Approved/.
---

# Process Approvals

Execute actions for files the human has approved by moving them to `/Pending_Approval/Approved/`.

## Instructions

### Step 1: Scan /Approved/
List all `.md` files in `AI_Employee_Vault/Pending_Approval/Approved/` (skip README.md).
If empty → log "No approvals to process" and stop.

### Step 2: For Each Approved File

Read the frontmatter fields, then route by `action:`:

#### `action: send_email`

Use the **local gmail MCP `mcp__gmail__send_email` tool** — do NOT use the claude.ai Gmail integration.

Extract from frontmatter: `to`, `subject`, `thread_id`, `in_reply_to`

Get the email body:
- If `body_file:` is set → read that file, extract plain text (strip frontmatter + `*Drafted by` footer)
- If `body:` is set inline → use directly

Call:
```
mcp__gmail__send_email(to, subject, body, thread_id="", in_reply_to="")
```

On success: move approved file to `AI_Employee_Vault/Done/`, log result.
On error: log error, do NOT move file, add alert to Dashboard.md.

#### `action: post_linkedin`
```bash
python actions/post_linkedin.py "<approved_file_path>"
```
Posts via Playwright. Moves file to /Done/ on success.

#### `action: post_facebook`

Use the **local facebook MCP `mcp__facebook__post_facebook` tool**.

Extract from frontmatter or `## Post Content` section: the `message` to post.

Call:
```
mcp__facebook__post_facebook(message=<post_text>)
```

On success: move approved file to `AI_Employee_Vault/Done/`, log result.
On error: log error, do NOT move file, add alert to Dashboard.md.

#### `action: post_instagram`

Use the **local facebook MCP `mcp__facebook__post_instagram` tool**.

Extract from frontmatter:
- `image_url:` — image URL (may be empty — warn if so but attempt with empty string)
- From `## Post Content` section: the caption text

Call:
```
mcp__facebook__post_instagram(caption=<caption_text>, image_url=<image_url or "">)
```

On success: move approved file to `AI_Employee_Vault/Done/`, log result.
On error: log error, do NOT move file.

#### `action: post_facebook_comment`

Use the **local facebook MCP `mcp__facebook__post_comment` tool**.

Extract from frontmatter:
- `post_id:` — Facebook post ID, usually `<page_id>_<post_id>`

Extract the comment body from either:
- `comment:` frontmatter field
- `## Comment` section

Call:
```
mcp__facebook__post_comment(post_id=<post_id>, message=<comment_text>)
```

On success: move approved file to `AI_Employee_Vault/Done/`, log result.
On error: log error, do NOT move file.

#### `action: unknown` or unrecognized
- Log: "Unknown action type in <filename> — manual handling required"
- Move file to `AI_Employee_Vault/Pending_Approval/Rejected/` with a note

### Step 3: Update the Related Task

Find related Needs_Action or Plans file (check `related_task:` frontmatter field).
- If original task is in Needs_Action → move to Done/ with a Resolution note
- Update `status:` → `done`

### Step 4: Update Dashboard and Log

Update `AI_Employee_Vault/Dashboard.md`:
- Decrement "Items in /Pending_Approval"
- Increment "Items Completed Today"
- Add to Recent Activity

Append to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.md`:
```markdown
### <HH:MM:SS> — approval_executed
- **file:** <approval filename>
- **action:** <action type>
- **result:** success / error
- **details:** <message_id or post_id or error text>
```

## Error Handling
- If MCP tool or script fails → log error, do NOT delete approval file, alert in Dashboard
- If credentials missing (Facebook not configured) → log clearly, move file to Rejected/ with reason
- If DRY_RUN=true → MCP tools log "[DRY RUN]" automatically; LinkedIn script logs "would post"
