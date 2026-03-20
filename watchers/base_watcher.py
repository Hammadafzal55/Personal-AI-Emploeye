"""
base_watcher.py — Abstract base class for all AI Employee Watchers.

All Watchers follow the same pattern:
  1. check_for_updates() → detect new items from a source
  2. create_action_file(item) → write a .md file to /Needs_Action
  3. run() → loop forever, sleeping between checks
"""

import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime


def setup_logging(name: str, log_level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


class BaseWatcher(ABC):
    """
    Abstract base for all Watchers. Subclass this and implement:
      - check_for_updates() -> list of items to process
      - create_action_file(item) -> Path of the created .md file
    """

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.check_interval = check_interval
        self.logger = setup_logging(self.__class__.__name__)
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create required vault folders if they don't exist."""
        for folder in ["Needs_Action", "Inbox", "Done", "Plans", "Logs", "Pending_Approval"]:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

    def log_action(self, action_type: str, details: dict):
        """Append an action entry to today's log file."""
        log_dir = self.vault_path / "Logs"
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"

        entry = (
            f"\n### {datetime.now().strftime('%H:%M:%S')} — {action_type}\n"
            + "\n".join(f"- **{k}:** {v}" for k, v in details.items())
            + "\n"
        )

        with open(log_file, "a", encoding="utf-8") as f:
            if not log_file.exists() or log_file.stat().st_size == 0:
                f.write(f"# Action Log — {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(entry)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return a list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create a .md action file in /Needs_Action and return its path."""
        pass

    def run(self):
        self.logger.info(
            f"Starting {self.__class__.__name__} — checking every {self.check_interval}s"
        )
        while True:
            try:
                items = self.check_for_updates()
                self.logger.info(f"Found {len(items)} new email(s)")
                for item in items:
                    path = self.create_action_file(item)
                    if path is None:
                        continue  # item was skipped (e.g. SENT email)
                    self.logger.info(f"Created action file: {path.name}")
                    self.log_action(
                        "action_file_created",
                        {"watcher": self.__class__.__name__, "file": path.name},
                    )
            except KeyboardInterrupt:
                self.logger.info("Stopped by user (KeyboardInterrupt).")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)

            time.sleep(self.check_interval)
