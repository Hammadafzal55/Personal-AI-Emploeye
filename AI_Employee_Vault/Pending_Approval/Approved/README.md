# /Approved — Human-Approved Actions

Move approval files **from `/Pending_Approval/`** into this folder to authorize Claude to execute the action.

The orchestrator's `/Approved/` watcher detects new files here instantly and calls the appropriate action script automatically:

| `action:` field | Script called |
|---|---|
| `send_email` | `actions/send_email.py` |
| `post_linkedin` | `actions/post_linkedin.py` |
| `payment` | *(Gold tier — not yet implemented)* |

After execution, the file is moved to `/Done/` automatically.
