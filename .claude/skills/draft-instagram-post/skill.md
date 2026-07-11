---
name: draft-instagram-post
description: |
  Draft an Instagram caption for the Business/Creator account.
  Routes to /Pending_Approval/ for human review before posting.
  Use when: scheduled Instagram posting time (11:00 PKT), or user asks to draft an Instagram post.
---

# Draft Instagram Post

Create a punchy, hashtag-rich Instagram caption. Instagram is visual-first — the caption
supports the image. Since image generation is not yet automated, include an image suggestion
in the frontmatter for the human to source or create.

## Instructions

### Step 1: Load Context
1. Read `AI_Employee_Vault/Company_Handbook.md` Section 10 — brand voice, audience.
2. Read `AI_Employee_Vault/Business_Goals.md` for content pillars.
3. Check `AI_Employee_Vault/Pending_Approval/` for INSTAGRAM_*.md from today — skip if one exists (max 1/day).

### Step 2: Choose a Topic

Same 3 content pillars, adapted for Instagram's visual + quick-hit format:

| Pillar | Instagram Angle |
|---|---|
| AI & Automation | One punchy insight, "did you know?" fact, or before/after comparison |
| New Tech Launches | "What just dropped and why it matters" — concise hype + context |
| Career & Learning | Quick tip, tool recommendation, or mindset shift |

### Step 3: Write the Caption

- **Length:** 100–200 words (shorter is better on Instagram)
- **Format:**
  - Line 1: Hook — make people tap "more" (bold claim, emoji, question)
  - Lines 2–5: 2-3 short punchy paragraphs with line breaks
  - CTA: "Save this post" / "Share with a dev friend" / "What do you think? 👇"
  - Hashtags: 10–15 relevant tags on the last line
- **Emojis:** Use sparingly — 1-2 per paragraph max
- **Tone:** Energetic, confident, relatable

### Step 4: Choose an Image Suggestion

Write a one-sentence description of the ideal image for this post.
Examples:
- "Dark-themed code screenshot showing an AI agent loop"
- "Clean infographic: 3-step agentic workflow diagram"
- "Split image: human vs AI employee comparison table"

### Step 5: Create Approval Request

Save to `AI_Employee_Vault/Pending_Approval/INSTAGRAM_<ShortTopic>_<YYYY-MM-DD>.md`:

```markdown
---
type: approval_request
action: post_instagram
topic: <topic name>
pillar: <content pillar>
image_suggestion: <one-sentence image description for human to source>
image_url: ""
created: <ISO timestamp>
expires: <ISO timestamp + 48h>
status: pending
---

## Post Content

<Full Instagram caption including hashtags — exactly as it will be posted>

## Image Required
Please add a public image URL to the `image_url` field above before approving.
Suggestion: <image_suggestion>

## To Approve
1. Add `image_url` to frontmatter above
2. Move this file to `/Pending_Approval/Approved/`

## To Reject / Edit
Move to `/Pending_Approval/Rejected/` or edit the caption before approving.
```

### Step 6: Update Dashboard
- Add Recent Activity row: `Instagram post drafted — <topic>`
- Increment Approvals Pending count

## Rules
- Maximum 1 Instagram draft per day
- image_url field must be filled by the human before the post can be approved
- Never repeat a topic from Done/INSTAGRAM_*.md in the last 7 days
