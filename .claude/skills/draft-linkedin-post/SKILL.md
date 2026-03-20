---
name: draft-linkedin-post
description: |
  Generate a professional LinkedIn post to promote the business and generate leads.
  Reads Business_Goals.md and Company_Handbook.md for context, drafts a post,
  and routes it to /Pending_Approval/ for human review before publishing.
  Use when: scheduled LinkedIn posting time arrives, or user asks to "draft a LinkedIn post".
---

# Draft LinkedIn Post

Generate a LinkedIn post aligned with the business goals and brand voice, then route for approval.

## Instructions

### Step 1: Load Business Context
1. Read `AI_Employee_Vault/Company_Handbook.md` → note brand voice (Section 6), business info (Section 10).
2. Read `AI_Employee_Vault/Business_Goals.md` → identify current focus areas, projects, metrics.
3. Read `AI_Employee_Vault/Done/` → scan last 7 days of completed tasks for content ideas.

### Step 2: Choose a Post Type

Select one of these post types based on what's most relevant this week:

| Type | When to Use | Example Hook |
|------|-------------|--------------|
| **Value / Tip** | Always safe | "3 things I learned about [topic]..." |
| **Win / Case Study** | After a project milestone | "We just helped a client achieve X..." |
| **Behind the Scenes** | When building something new | "Here's how we built our AI Employee in a weekend..." |
| **Question / Poll** | Engagement needed | "What's the biggest challenge in [industry]?" |
| **Announcement** | New service/product | "Excited to announce..." |

### Step 3: Write the Post

Follow LinkedIn best practices:
- **Hook** (line 1): Bold statement or question — makes people click "See more"
- **Body**: 3–5 short paragraphs, each 1–3 lines. Use line breaks liberally.
- **CTA**: End with a clear call to action (comment, DM, visit website)
- **Hashtags**: 3–5 relevant hashtags at the end
- **Length**: 150–300 words (optimal engagement range)
- **Tone**: Professional but warm. First person. No jargon.

### Step 4: Create Approval Request

Save to `AI_Employee_Vault/Pending_Approval/LINKEDIN_<topic>_<date>.md`:
```markdown
---
type: approval_request
action: post_linkedin
post_type: <value_tip|win|behind_scenes|question|announcement>
created: <ISO timestamp>
expires: <ISO timestamp + 48h>
status: pending
estimated_reach: organic
---

## Post Content

<The full LinkedIn post text, ready to copy-paste or auto-post>

## Hashtags
<#tag1 #tag2 #tag3>

## Rationale
<Why this post now — what business goal it serves>

## To Approve
Move this file to `/Pending_Approval/Approved/`
The orchestrator will call `actions/post_linkedin.py` to post automatically.

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text above before approving.
```

### Step 5: Update Dashboard
- Update "Items in /Pending_Approval": +1
- Add to Recent Activity

## Rules
- NEVER post political opinions, personal opinions, or controversial statements
- NEVER post client names or confidential project details without permission
- Always align with the brand voice in Company_Handbook.md Section 6
- Maximum 1 post per day to avoid spam perception
- If Business_Goals.md Section 10 is still placeholder → write a QUESTION file asking the user to fill it in first
