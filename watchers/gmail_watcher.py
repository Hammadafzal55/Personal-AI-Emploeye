"""
gmail_watcher.py — Watches Gmail for unread important emails.

When a new important/unread email is found, creates an EMAIL_<id>.md
action file in /Needs_Action for Claude to process.

Setup (one-time):
    1. Create a Google Cloud project at console.cloud.google.com
    2. Enable the Gmail API
    3. Create OAuth 2.0 credentials (Desktop app) → download as credentials.json
    4. Place credentials.json at path in GMAIL_CREDENTIALS_PATH env var
    5. Run: python setup/gmail_oauth_setup.py  (generates token.json)
    6. Set GMAIL_TOKEN_PATH env var to token.json location

Usage:
    python watchers/gmail_watcher.py
    (or launched automatically by orchestrator.py)
"""

import os
import sys
import json
import base64
import email as email_lib
from pathlib import Path
from datetime import datetime

# Append parent dir so we can import base_watcher
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from watchers.base_watcher import BaseWatcher, setup_logging

logger = setup_logging("GmailWatcher")

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
CREDENTIALS_PATH = Path(os.getenv("GMAIL_CREDENTIALS_PATH", str(_PROJECT_ROOT / "secrets/gmail_credentials.json")))
TOKEN_PATH = Path(os.getenv("GMAIL_TOKEN_PATH", str(_PROJECT_ROOT / "secrets/gmail_token.json")))
GMAIL_QUERY = os.getenv("GMAIL_QUERY", "is:unread newer_than:7d")
CHECK_INTERVAL = int(os.getenv("GMAIL_CHECK_INTERVAL", "120"))

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

PROCESSED_IDS_PATH = Path(os.getenv("GMAIL_PROCESSED_IDS_PATH", str(_PROJECT_ROOT / "secrets/gmail_processed_ids.json")))
HISTORY_ID_PATH = Path(os.getenv("GMAIL_HISTORY_ID_PATH", str(_PROJECT_ROOT / "secrets/gmail_history_id.json")))


def load_processed_ids() -> set:
    if PROCESSED_IDS_PATH.exists():
        try:
            return set(json.loads(PROCESSED_IDS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_processed_ids(ids: set):
    PROCESSED_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_IDS_PATH.write_text(json.dumps(list(ids)), encoding="utf-8")


def load_history_id() -> str | None:
    if HISTORY_ID_PATH.exists():
        try:
            return json.loads(HISTORY_ID_PATH.read_text(encoding="utf-8")).get("historyId")
        except Exception:
            pass
    return None


def save_history_id(history_id: str | None):
    if history_id is None:
        if HISTORY_ID_PATH.exists():
            HISTORY_ID_PATH.unlink()
        return
    HISTORY_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_ID_PATH.write_text(json.dumps({"historyId": history_id}), encoding="utf-8")


def load_credentials() -> "Credentials | None":
    """Load and refresh Gmail OAuth credentials."""
    if not TOKEN_PATH.exists():
        logger.error(
            f"Gmail token not found at {TOKEN_PATH}. "
            "Run: python setup/gmail_oauth_setup.py"
        )
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            return None

    return creds


def _decode_part(data: str) -> str:
    """Base64-decode a Gmail message part."""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    """Very lightweight HTML tag stripper — no external deps."""
    import re
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_from_parts(parts: list, mime_pref: str) -> str:
    """Recursively search parts for a given MIME type."""
    for part in parts:
        if part.get("mimeType") == mime_pref:
            data = part.get("body", {}).get("data", "")
            if data:
                return _decode_part(data)
        # Recurse into multipart/* containers
        if "parts" in part:
            result = _extract_from_parts(part["parts"], mime_pref)
            if result:
                return result
    return ""


def decode_body(payload: dict) -> str:
    """Extract readable text from Gmail message payload.
    Tries plain text first; falls back to stripped HTML."""
    body = ""

    if "parts" in payload:
        # Try plain text first
        body = _extract_from_parts(payload["parts"], "text/plain")
        # Fall back to HTML if no plain text found
        if not body:
            html = _extract_from_parts(payload["parts"], "text/html")
            if html:
                body = _strip_html(html)
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            raw = _decode_part(data)
            mime = payload.get("mimeType", "")
            body = _strip_html(raw) if "html" in mime else raw

    # Trim to first 800 chars to keep action files readable
    return body.strip()[:800] if body else ""


class GmailWatcher(BaseWatcher):
    """Polls Gmail for unread important emails and creates action files."""

    def __init__(self, vault_path: str = str(VAULT_PATH)):
        super().__init__(vault_path, check_interval=CHECK_INTERVAL)
        self.processed_ids: set[str] = load_processed_ids()
        self.logger.info(f"Loaded {len(self.processed_ids)} previously processed email IDs.")
        self.service = None
        self._init_service()

    def _init_service(self):
        if not GOOGLE_AVAILABLE:
            self.logger.error(
                "Google API libraries not installed. Run: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return

        creds = load_credentials()
        if creds:
            self.service = build("gmail", "v1", credentials=creds)
            self.logger.info("Gmail service initialized successfully.")

    def _get_current_history_id(self) -> str | None:
        """Fetch the mailbox's current historyId via getProfile."""
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return profile.get("historyId")
        except Exception as e:
            self.logger.error(f"Failed to get current historyId: {e}")
            return None

    def _full_scan(self) -> list:
        """First run: anchor at the current historyId — do NOT backfill old emails.
        Only emails that arrive AFTER this point will be picked up."""
        history_id = self._get_current_history_id()
        if history_id:
            save_history_id(history_id)
            self.logger.info(
                f"Anchored at historyId {history_id}. "
                "Watching for NEW emails only — old unread emails will not be surfaced."
            )
        else:
            self.logger.warning("Could not fetch historyId — will retry on next poll.")
        return []  # Never backfill old emails on startup

    def check_for_updates(self) -> list:
        if not self.service:
            return []

        history_id = load_history_id()

        # --- Incremental path: use History API to get only truly new messages ---
        if history_id:
            try:
                response = self.service.users().history().list(
                    userId="me",
                    startHistoryId=history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                ).execute()

                new_messages = []
                for record in response.get("history", []):
                    for item in record.get("messagesAdded", []):
                        msg_id = item["message"]["id"]
                        if msg_id not in self.processed_ids:
                            new_messages.append({"id": msg_id})

                # Advance the stored historyId to the latest
                if "historyId" in response:
                    save_history_id(response["historyId"])

                if new_messages:
                    self.logger.info(f"History API: {len(new_messages)} new message(s) since last check.")
                return new_messages

            except Exception as e:
                err = str(e)
                if "404" in err or "startHistoryId" in err or "invalid" in err.lower():
                    # historyId expired (Gmail keeps ~7 days). Fall back to full scan.
                    self.logger.warning("historyId expired or invalid — falling back to full scan.")
                    save_history_id(None)  # clear stale ID
                    import os as _os; _os.remove(str(HISTORY_ID_PATH)) if HISTORY_ID_PATH.exists() else None
                    return self._full_scan()
                self.logger.error(f"Gmail History API error: {e}")
                return []

        # --- First run: no historyId yet, do a full scan ---
        self.logger.info("No historyId found — performing initial full scan.")
        return self._full_scan()

    def create_action_file(self, message: dict) -> Path:
        msg_id = message["id"]

        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            self.logger.error(f"Failed to fetch message {msg_id}: {e}")
            self.processed_ids.add(msg_id)
            return self.needs_action / f"EMAIL_{msg_id}_error.md"

        labels = msg.get("labelIds", [])

        # Skip outgoing emails — the owner's own sent replies show up via History API
        # when their thread receives a new message. We never want to draft a reply to ourselves.
        if "SENT" in labels:
            self.processed_ids.add(msg_id)
            save_processed_ids(self.processed_ids)
            self.logger.info(f"Skipped SENT email {msg_id} (owner's outgoing reply — not an inbox task)")
            return None

        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", datetime.now().isoformat())
        internet_message_id = headers.get("Message-ID", "")
        snippet = msg.get("snippet", "")
        body = decode_body(msg["payload"])
        thread_id = msg.get("threadId", "")

        # Determine priority from labels
        priority = "high" if "IMPORTANT" in labels else "normal"

        content = f"""---
type: email
message_id: {msg_id}
thread_id: {thread_id}
internet_message_id: {internet_message_id}
from: {sender}
subject: {subject}
received: {date}
priority: {priority}
labels: {", ".join(labels)}
status: pending
---

# Email: {subject}

**From:** {sender}
**Received:** {date}
**Priority:** {priority}

## Snippet
{snippet}

## Body
{body if body else "*(body not extracted — check Gmail directly)*"}

## Suggested Actions
- [ ] Read and understand the email
- [ ] Draft a reply (requires approval before sending)
- [ ] Forward to relevant party if needed
- [ ] Archive / mark as read after processing

## Notes for Claude
> Draft a reply using the `draft-email-reply` skill.
> The reply must go to /Pending_Approval/ before sending.
> Never send to new contacts without explicit approval.
"""

        filepath = self.needs_action / f"EMAIL_{msg_id}.md"
        filepath.write_text(content, encoding="utf-8")
        self.processed_ids.add(msg_id)
        save_processed_ids(self.processed_ids)

        # Mark as read in Gmail so it won't re-appear in is:unread queries
        try:
            self.service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception as e:
            self.logger.warning(f"Could not mark email as read: {e}")

        self.log_action(
            "email_detected",
            {"from": sender, "subject": subject[:60], "action_file": filepath.name},
        )

        return filepath


def main():
    if not GOOGLE_AVAILABLE:
        logger.error("Install Google libraries: pip install google-auth google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    watcher = GmailWatcher()
    if not watcher.service:
        logger.error("Gmail service failed to initialize. Check credentials and run gmail_oauth_setup.py.")
        sys.exit(1)

    watcher.run()


if __name__ == "__main__":
    main()
