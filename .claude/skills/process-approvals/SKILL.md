---
name: process-approvals
description: |
  Process files that have been moved to /Pending_Approval/Approved/ by the human.
  Reads each approved file, determines the action type, and executes the appropriate
  action script (send_email, post_linkedin, etc.). Logs results and moves files to /Done/.
  Use when: orchestrator detects new files in /Pending_Approval/Approved/.
---

# Process Approvals

Execute actions for files the human has approved by moving them to `/Pending_Approval/Approved/`.

## Instructions

### Step 1: Scan /Approved/
List all `.md` files in `AI_Employee_Vault/Pending_Approval/Approved/` (skip README.md).
If empty → log "No approvals to process" and stop.

### Step 2: For Each Approved File

Read the frontmatter `action:` field and route accordingly:

#### `action: send_email`
```bash
python actions/send_email.py "<approved_file_path>"
```
- The script sends the email via Gmail API
- Moves the file to /Done/ on success
- Logs result to /Logs/

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
- If action script fails → log error, do NOT delete approval file, alert in Dashboard
- If DRY_RUN=true → log "would execute" but don't call action scripts
