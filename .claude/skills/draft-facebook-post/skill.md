---
name: draft-facebook-post
description: |
  Draft a Facebook Page post about AI, tech, or business topics.
  Routes to /Pending_Approval/ for human review before posting.
  Use when: scheduled Facebook posting time (10:00 PKT), or user asks to draft a Facebook post.
---

# Draft Facebook Post

Create a valuable, engaging Facebook Page post. Facebook allows longer-form content than LinkedIn —
use this for deeper insights, mini-guides, or story-driven posts.

## Instructions

### Step 1: Load Context
1. Read `AI_Employee_Vault/Company_Handbook.md` Section 10 — brand voice, content pillars, audience.
2. Read `AI_Employee_Vault/Business_Goals.md` — LinkedIn content strategy (same pillars apply).
3. Scan `AI_Employee_Vault/Done/` for files modified in the last 7 days — any milestones worth sharing.
4. Check `AI_Employee_Vault/Pending_Approval/` for any FACEBOOK_*.md from today — if one exists already, skip (max 1/day).

### Step 2: Choose a Topic

Same 3 content pillars as LinkedIn, but adapt for Facebook's more conversational style:

| Pillar | Facebook Angle |
|---|---|
| AI & Automation | Real-world use cases, "how I built X" stories, lessons learned |
| New Tech Launches | Deeper explainers — what it means for businesses and devs |
| Career & Learning | Practical guides, mini-tutorials, "things I wish I knew" format |

**NEVER post:** promotional content, political opinions, the hackathon project by name.

### Step 3: Write the Post

- **Length:** 200–400 words (Facebook rewards longer, story-driven posts)
- **Format:** Short paragraphs (2-3 lines), line breaks between ideas, no bullet overload
- **Hook:** First line must stop the scroll — bold claim, question, or surprising stat
- **Body:** Tell a mini-story or walk through a concept step by step
- **CTA:** End with a question or call to share
- **Hashtags:** 3–5 tags only (Facebook penalises hashtag stuffing)
- **Tone:** Warm, knowledgeable, first-person — like talking to a smart friend

### Step 4: Create Approval Request

Save to `AI_Employee_Vault/Pending_Approval/FACEBOOK_<ShortTopic>_<YYYY-MM-DD>.md`:

```markdown
---
type: approval_request
action: post_facebook
topic: <topic name>
pillar: <content pillar>
created: <ISO timestamp>
expires: <ISO timestamp + 48h>
status: pending
---

## Post Content

<Full Facebook post text exactly as it will be posted, including hashtags>

## To Approve
Move this file to `/Pending_Approval/Approved/`

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text before approving.
```

### Step 5: Update Dashboard
- Add Recent Activity row: `Facebook post drafted — <topic>`
- Increment Approvals Pending count

## Rules
- Maximum 1 Facebook post draft per day
- Never repeat a topic from Done/FACEBOOK_*.md in the last 7 days
- Post must deliver standalone value — reader learns something without needing context
