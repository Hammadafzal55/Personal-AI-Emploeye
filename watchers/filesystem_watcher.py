"""
filesystem_watcher.py — Watches the AI_Employee_Vault/Inbox folder for new files.

When a file is dropped into /Inbox, this watcher:
  1. Detects it using the watchdog library.
  2. Reads basic metadata (name, size, type).
  3. Creates a FILE_<name>.md action item in /Needs_Action.
  4. Claude Code will process /Needs_Action on its next run.

Usage:
    python watchers/filesystem_watcher.py

Requirements:
    pip install watchdog
"""

import os
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FilesystemWatcher] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("FilesystemWatcher")


logger = setup_logging()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
INBOX_PATH = VAULT_PATH / "Inbox"
NEEDS_ACTION_PATH = VAULT_PATH / "Needs_Action"
LOGS_PATH = VAULT_PATH / "Logs"

# Files to ignore inside the Inbox (meta / system files)
IGNORED_FILENAMES = {"README.md", ".gitkeep", ".DS_Store", "Thumbs.db"}
IGNORED_EXTENSIONS = {".tmp", ".part", ".crdownload"}


def _safe_name(filename: str) -> str:
    """Strip characters that are unsafe in markdown filenames."""
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in filename).strip()


def _file_type_hint(extension: str) -> str:
    hints = {
        ".md": "Markdown note",
        ".txt": "Plain text document",
        ".csv": "Spreadsheet / data file",
        ".pdf": "PDF document",
        ".docx": "Word document",
        ".xlsx": "Excel spreadsheet",
        ".png": "Image file",
        ".jpg": "Image file",
        ".jpeg": "Image file",
    }
    return hints.get(extension.lower(), "Unknown file type")


def _append_log(action_type: str, details: dict):
    """Append an entry to today's log file."""
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_PATH / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    entry = (
        f"\n### {datetime.now().strftime('%H:%M:%S')} — {action_type}\n"
        + "\n".join(f"- **{k}:** {v}" for k, v in details.items())
        + "\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        if log_file.stat().st_size == 0 if log_file.exists() else True:
            f.write(f"# Action Log — {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(entry)


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

class InboxDropHandler(FileSystemEventHandler):
    """Handles new file events in the /Inbox folder."""

    def __init__(self):
        super().__init__()
        self._processing: set[str] = set()  # debounce: track in-flight paths

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_new_file(Path(event.src_path))

    def on_moved(self, event):
        """Also handle files moved/renamed into the Inbox."""
        if event.is_directory:
            return
        dest = Path(event.dest_path)
        if dest.parent.resolve() == INBOX_PATH.resolve():
            self._handle_new_file(dest)

    def _handle_new_file(self, source: Path):
        # Ignore system / temp files
        if source.name in IGNORED_FILENAMES:
            return
        if source.suffix.lower() in IGNORED_EXTENSIONS:
            return
        if source.name.startswith("."):
            return

        # Debounce: some editors write files in multiple bursts
        if str(source) in self._processing:
            return
        self._processing.add(str(source))

        # Small delay to let the writer finish flushing
        time.sleep(0.5)

        try:
            self._create_action_file(source)
        finally:
            self._processing.discard(str(source))

    def _create_action_file(self, source: Path):
        """Create a Needs_Action markdown file describing the dropped file."""
        NEEDS_ACTION_PATH.mkdir(parents=True, exist_ok=True)

        safe = _safe_name(source.stem)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        action_filename = f"FILE_{safe}_{timestamp}.md"
        action_path = NEEDS_ACTION_PATH / action_filename

        try:
            size_bytes = source.stat().st_size
            size_display = (
                f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
            )
        except FileNotFoundError:
            logger.warning(f"File disappeared before we could stat it: {source}")
            return

        content = f"""---
type: file_drop
source: Inbox/{source.name}
original_name: {source.name}
extension: {source.suffix.lower()}
file_type: {_file_type_hint(source.suffix)}
size: {size_display}
received: {datetime.now().isoformat()}
status: pending
---

# New File: {source.name}

A file was dropped into the **Inbox** and requires processing.

## File Details
- **Name:** `{source.name}`
- **Type:** {_file_type_hint(source.suffix)}
- **Size:** {size_display}
- **Location:** `AI_Employee_Vault/Inbox/{source.name}`

## Suggested Actions
- [ ] Read or summarize the file content
- [ ] Determine the appropriate response or action
- [ ] If action requires approval, write to `/Pending_Approval/`
- [ ] Log the outcome to `/Logs/`
- [ ] Move this task file to `/Done/` when complete

## Notes for Claude
> Check `Company_Handbook.md` for rules on how to handle this file type.
> If the file contains financial data (CSV), cross-reference with `Business_Goals.md`.
"""

        action_path.write_text(content, encoding="utf-8")
        logger.info(f"Created action file: {action_filename} (source: {source.name})")

        _append_log(
            "file_drop_detected",
            {
                "source": source.name,
                "action_file": action_filename,
                "size": size_display,
            },
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Ensure required directories exist
    INBOX_PATH.mkdir(parents=True, exist_ok=True)
    NEEDS_ACTION_PATH.mkdir(parents=True, exist_ok=True)
    LOGS_PATH.mkdir(parents=True, exist_ok=True)

    logger.info(f"Vault path:  {VAULT_PATH}")
    logger.info(f"Watching:    {INBOX_PATH}")
    logger.info(f"Action dest: {NEEDS_ACTION_PATH}")

    event_handler = InboxDropHandler()
    observer = Observer()
    observer.schedule(event_handler, str(INBOX_PATH), recursive=False)
    observer.start()

    logger.info("Filesystem Watcher is running. Drop files into /Inbox to trigger actions.")
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()

    observer.join()
    logger.info("Filesystem Watcher stopped.")


if __name__ == "__main__":
    main()
