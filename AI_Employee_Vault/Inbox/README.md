# /Inbox — File Drop Zone

Drop any file here. The Filesystem Watcher will detect it, create an action item in `/Needs_Action/`, and Claude will process it on the next run.

## Supported File Types
- `.md` — Markdown notes, tasks, messages
- `.txt` — Plain text
- `.csv` — Data files (transactions, contacts)
- `.pdf` — Documents (Claude will summarize)
- Any other file — Will be logged and flagged for review

## How It Works
1. You drop a file here.
2. `filesystem_watcher.py` detects the new file.
3. It creates a `FILE_<name>.md` action item in `/Needs_Action/`.
4. Claude reads the action item and processes it.
5. The original file stays here; the action item moves to `/Done/` when complete.
