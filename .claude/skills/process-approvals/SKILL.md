---
name: process-approvals
description: |
  Process files that have been moved to /Pending_Approval/Approved/ by the human.
  Reads each approved file, determines the action type, and executes the appropriate
  action (MCP tool for send_email, Python script for post_linkedin). Logs results and
  moves files to /Done/.
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

Use the **gmail MCP `send_email` tool** — do NOT run any Python script.

Extract these fields from the approved file's frontmatter:
- `to:` — recipient email address
- `subject:` — email subject
- `thread_id:` — Gmail thread ID (optional, for replies)
- `in_reply_to:` — Message-ID of original email (optional, for replies)

Get the email body:
- If `body_file:` is set → read that file and extract the plain text body:
  - Strip any YAML frontmatter (`--- ... ---`)
  - If the file has a `## Draft Reply` section, use only the content under that heading
  - Strip any trailing AI footer (lines starting with `---` followed by `*Drafted by`)
- If `body:` is set inline → use it directly

Then call the MCP tool:
```
gmail.send_email(
  to=<to>,
  subject=<subject>,
  body=<plain text body>,
  thread_id=<thread_id or "">,
  in_reply_to=<in_reply_to or "">
)
```

On success:
- Move the approved file to `AI_Employee_Vault/Done/`
- Log result

On error:
- Log the error
- Do NOT delete or move the approved file
- Add an alert row to Dashboard.md

#### `action: post_linkedin`
```bash
python actions/post_linkedin.py "<approved_file_path>"
```
- Posts to LinkedIn via Playwright
- Moves file to /Done/ on success
- Logs result to /Logs/

#### `action: unknown` or unrecognized
- Log: "Unknown action type in <filename> — manual handling required"
- Move file to `AI_Employee_Vault/Pending_Approval/Rejected/` with a note

### Step 3: Update the Related Task

Find the related Needs_Action or Plans file (check `related_task:` frontmatter field).
- If the original task is in Needs_Action → now move it to Done/ with a Resolution note
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
```

## Error Handling
- If MCP tool or script fails → log error, do NOT delete approval file, alert in Dashboard
- If DRY_RUN=true → gmail MCP logs "[DRY RUN]" automatically; LinkedIn script logs "would post"
