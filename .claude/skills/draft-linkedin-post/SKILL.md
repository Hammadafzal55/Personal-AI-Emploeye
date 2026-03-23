---
name: draft-linkedin-post
description: |
  Generate a professional LinkedIn post about trending tech, new launches,
  web dev news, or industry guides. Also scans vault progress for relevant wins.
  Routes to /Pending_Approval/ for review before publishing.
  Use when: scheduled LinkedIn posting time arrives, or user asks to "draft a LinkedIn post".
---

# Draft LinkedIn Post

Create a valuable, engaging LinkedIn post on a trending tech or web development topic.
Always lead with value — educate, inform, or inspire the reader.

## Instructions

### Step 1: Load Context

1. Read `AI_Employee_Vault/Company_Handbook.md` Section 10 — brand voice, content pillars, target audience.
2. Read `AI_Employee_Vault/Business_Goals.md` — LinkedIn content strategy and active projects.
3. Scan `AI_Employee_Vault/Done/` for files modified in the last 7 days — look for completed work, milestones, or solved problems worth sharing as a lesson.
4. Scan `AI_Employee_Vault/Briefings/` for the latest daily briefing — check for notable progress or insights.

### Step 2: Choose a Topic

**Priority order:**
1. **Vault progress first** — if a recent Done/ entry shows a meaningful milestone (built a feature, shipped something, solved a hard problem), turn it into a post. Frame it as a lesson or insight, NOT as promotion of the hackathon project.
2. **Trending tech topic** — use a content pillar below if no vault progress qualifies.

**Content pillars (check Done/LINKEDIN_*.md for last 7 days to avoid repeating a topic):**

| Pillar | Example Topics |
|---|---|
| New Tech Launch | New framework/library, major AI model update, OS or hardware launch |
| Web Dev Guide | CSS tips, JavaScript patterns, TypeScript, performance, accessibility, DevOps |
| AI & Automation | New AI tool, LLM update, prompt engineering tip, automation workflow |
| Industry News | Big tech news, developer survey results, open source milestone |
| Career & Learning | Skill roadmap, tool comparison, learning resource for developers |
| Open Source | Trending GitHub repo, useful CLI tool, developer utility worth sharing |

**NEVER post about:**
- The Personal AI Employee hackathon project by name
- Promotional content for services
- Political opinions or controversies

### Step 3: Write the Post

- **Hook** (line 1): Bold claim, surprising fact, or question — makes people click "See more"
- **Body**: 3–5 short paragraphs, 1–3 lines each, heavy line breaks
- **Value**: Teach one specific thing — tip, numbered list, or actionable insight
- **CTA**: End with a question to spark comments
- **Hashtags**: 4–6 tags (e.g. #WebDev #JavaScript #AI #OpenSource #TechNews)
- **Length**: 150–300 words
- **Tone**: Knowledgeable but conversational, first person, no jargon

### Step 4: Create Approval Request

Save to `AI_Employee_Vault/Pending_Approval/LINKEDIN_<ShortTopic>_<YYYY-MM-DD>.md`:

```markdown
---
type: approval_request
action: post_linkedin
topic: <topic name>
pillar: <content pillar>
inspired_by: <vault file if from progress scan, else "trending topic">
created: <ISO timestamp>
expires: <ISO timestamp + 48h>
status: pending
---

## Post Content

<Full LinkedIn post text exactly as it will be posted, including hashtags>

## To Approve
Move this file to `/Pending_Approval/Approved/`

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the post text before approving.
```

### Step 5: Update Dashboard
- Add Recent Activity row: `LinkedIn post drafted — <topic>`
- Increment Approvals Pending count

## Rules
- Maximum 1 post per day
- Never repeat a topic from Done/LINKEDIN_*.md in the last 7 days
- Post must deliver standalone value — reader learns something without needing context about who posted it
- If Company_Handbook.md Section 10 still has placeholder text, write a QUESTION file to /Needs_Action/ asking the owner to fill it in
