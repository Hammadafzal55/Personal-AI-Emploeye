---
name: process-inbox-tasks
description: |
  Process all pending items in the AI Employee Vault. Reads Company_Handbook.md
  for rules, processes each file in /Needs_Action, creates Plan files for
  multi-step tasks, routes sensitive actions to /Pending_Approval, and moves
  completed items to /Done. Updates Dashboard.md on completion.
  Use this whenever there are unprocessed items in Needs_Action, or when
  the user asks the AI Employee to "check inbox", "process tasks", or "do a run".
---

# Process Inbox Tasks

Process all pending items in `AI_Employee_Vault/Needs_Action/` following the rules in `Company_Handbook.md`.

## Instructions

### Step 1: Load Context
1. Read `AI_Employee_Vault/Company_Handbook.md` — your rules of engagement.
2. Read `AI_Employee_Vault/Dashboard.md` — current system status.
3. Read `AI_Employee_Vault/Business_Goals.md` — for business context.

### Step 2: Scan Needs_Action
List all `.md` files in `AI_Employee_Vault/Needs_Action/` (skip `README.md`).
If empty → update Dashboard.md with "Nothing to process" and stop.

### Step 3: Process Each Item

For **each** file in Needs_Action:

1. **Read** the file completely.
2. **Classify** the task type based on the `type:` frontmatter field:
   - `file_drop` → summarize file contents / determine action
   - `email` → draft a reply or categorize
   - `task` → execute the described task
   - `question` → write answer to Plans folder
3. **Decide** based on Company_Handbook.md autonomy thresholds:
   - **Auto-approve** (act immediately): summarizing, organizing, drafting, logging
   - **Requires approval**: sending email, payment, posting to social media

4. **For auto-approved actions:**
   - Execute the action.
   - Edit the file's frontmatter: change `status: pending` → `status: done`.
   - Tick all completed checkboxes: `- [ ]` → `- [x]`.
   - Append a `## Resolution` section if not already present.
   - Move the file to `AI_Employee_Vault/Done/`.

5. **For approval-required actions:**
   - Write a new file to `AI_Employee_Vault/Pending_Approval/` using this format:
     ```markdown
     ---
     type: approval_request
     action: <action_type>
     created: <ISO timestamp>
     expires: <ISO timestamp + 24h>
     status: pending
     related_task: Needs_Action/<original_filename>.md
     ---

     ## Action Details
     <What you want to do and why>

     ## To Approve
     Move this file to /Pending_Approval/Approved/

     ## To Reject
     Move this file to /Pending_Approval/Rejected/
     ```
   - Leave the original Needs_Action file in place (do NOT move to Done yet).
   - Note in the Needs_Action file: `awaiting_approval: true`

6. **For multi-step tasks**, create a plan file first:
   ```markdown
   # Plan: <Task Name>
   ---
   created: <ISO timestamp>
   related_task: Needs_Action/<filename>.md
   status: in_progress
   ---

   ## Objective
   <Clear goal>

   ## Steps
   - [x] Step 1 (done)
   - [ ] Step 2
   - [ ] Step 3 (REQUIRES APPROVAL)
   ```

### Step 4: Log Everything

Append entries to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.md`:
```markdown
### <HH:MM:SS> — Task Processed
- **File:** <filename>
- **Action:** <what was done>
- **Result:** <success / pending_approval / error>
```

### Step 5: Update Dashboard

Update `AI_Employee_Vault/Dashboard.md`:
- Update "Items in /Needs_Action" count
- Update "Items Completed Today" count
- Add entries to "Recent Activity" section (newest first, keep last 10)
- Update `last_updated` frontmatter field to today's date

## Usage

```bash
# Manual trigger
claude --print "Run the process-inbox-tasks skill"

# Or in interactive Claude Code session
/process-inbox-tasks
```

## Completion Signal

Output `<done>ALL_TASKS_PROCESSED</done>` when all items have been handled.

## Error Handling

- Unreadable or malformed file → Move to `Needs_Action/UNCLEAR/` and log reason.
- Missing source file (for file_drop) → Log and move task to Done with note.
- Ambiguous intent → Write a `QUESTION_<topic>_<date>.md` in `/Pending_Approval/`.
