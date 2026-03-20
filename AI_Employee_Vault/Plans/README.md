# /Plans — Claude's Action Plans

When Claude receives a complex task, it writes a Plan file here before acting. Plans use checkboxes to track progress.

## Plan File Format
```markdown
---
created: YYYY-MM-DDTHH:MM:SSZ
related_task: Needs_Action/<filename>.md
status: in_progress | pending_approval | complete
---

## Objective
<What needs to be done>

## Steps
- [ ] Step 1
- [ ] Step 2 (REQUIRES APPROVAL)
- [ ] Step 3
```
