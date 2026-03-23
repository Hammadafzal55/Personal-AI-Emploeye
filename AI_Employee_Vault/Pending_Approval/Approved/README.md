# /Approved — Human-Approved Actions

Move approval files **from `/Pending_Approval/`** into this folder to authorize Claude to execute the action.

The orchestrator's `/Approved/` watcher detects new files here instantly and calls the appropriate executor automatically:

| `action:` field | Executor |
|---|---|
| `send_email` | `mcp_servers/gmail_mcp` — Claude uses the gmail MCP `send_email` tool |
| `post_linkedin` | `actions/post_linkedin.py` — Playwright script |
| `payment` | *(Gold tier — not yet implemented)* |

After execution, the file is moved to `/Done/` automatically.
