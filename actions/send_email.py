"""
send_email.py — Sends an email via Gmail API after human approval.

Called by orchestrator when an email approval file appears in /Approved/.
Reads the approval file, extracts email details, and sends via Gmail API.

Usage (internal — called by orchestrator):
    python actions/send_email.py <path_to_approval_file>

The approval file must have frontmatter:
    type: approval_request
    action: send_email
    to: recipient@example.com
    subject: Email Subject
    body_file: AI_Employee_Vault/Plans/draft_<name>.md  (optional)
    body: "Direct body text"  (used if body_file not set)
"""

import os
import sys
import base64
import logging
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SendEmail] %(levelname)s: %(message)s",
)
logger = logging.getLogger("SendEmail")

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
TOKEN_PATH = Path(os.getenv("GMAIL_TOKEN_PATH", "secrets/gmail_token.json"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def parse_frontmatter(file_path: Path) -> dict:
    """Parse YAML-style frontmatter from a markdown file."""
    content = file_path.read_text(encoding="utf-8")
    fields = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    fields[key.strip()] = value.strip()
            fields["_body_markdown"] = parts[2].strip()
    return fields


def get_gmail_service():
    if not GOOGLE_AVAILABLE:
        logger.error("Google libraries not installed.")
        return None
    if not TOKEN_PATH.exists():
        logger.error(f"Gmail token not found at {TOKEN_PATH}. Run: python setup/gmail_oauth_setup.py")
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def build_message(to: str, subject: str, body: str,
                  thread_id: str = "", in_reply_to: str = "") -> dict:
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}" if in_reply_to else subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return payload


def log_action(approval_file: Path, result: str, details: str = ""):
    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    entry = (
        f"\n### {datetime.now().strftime('%H:%M:%S')} — email_sent\n"
        f"- **approval_file:** {approval_file.name}\n"
        f"- **result:** {result}\n"
        f"- **dry_run:** {DRY_RUN}\n"
    )
    if details:
        entry += f"- **details:** {details}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def _extract_email_body(raw: str) -> str:
    """Strip YAML frontmatter, markdown headers, and AI footers from a draft file.
    Returns only the clean plain-text email body."""
    text = raw.strip()

    # Strip YAML frontmatter (--- ... ---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    # Extract content under "## Draft Reply" if present
    if "## Draft Reply" in text:
        text = text.split("## Draft Reply", 1)[1].strip()

    # Strip trailing AI footer (--- followed by *Drafted by AI Employee*)
    if "\n---" in text:
        text = text.rsplit("\n---", 1)[0].strip()

    return text


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: python actions/send_email.py <approval_file_path>")
        sys.exit(1)

    approval_path = Path(sys.argv[1])
    if not approval_path.exists():
        logger.error(f"Approval file not found: {approval_path}")
        sys.exit(1)

    fields = parse_frontmatter(approval_path)

    action = fields.get("action", "")
    if action != "send_email":
        logger.error(f"Wrong action type: {action}. Expected 'send_email'.")
        sys.exit(1)

    to = fields.get("to", "")
    subject = fields.get("subject", "No Subject")
    thread_id = fields.get("thread_id", "")
    in_reply_to = fields.get("in_reply_to", "")

    # Get body: either from a referenced draft file or inline
    body = fields.get("body", "")
    body_file_ref = fields.get("body_file", "")
    if body_file_ref and not body:
        body_path = VAULT_PATH.parent / body_file_ref
        if body_path.exists():
            body = _extract_email_body(body_path.read_text(encoding="utf-8"))
        else:
            logger.warning(f"body_file not found: {body_path}. Using inline body.")

    if not body:
        body = fields.get("_body_markdown", "")

    if not to:
        logger.error("No recipient (to:) found in approval file.")
        sys.exit(1)

    logger.info(f"Preparing to send email → To: {to} | Subject: {subject}")

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send email to: {to}")
        logger.info(f"[DRY RUN] Subject: {subject}")
        logger.info(f"[DRY RUN] Body preview: {body[:100]}...")
        log_action(approval_path, "dry_run_skipped")
        return

    service = get_gmail_service()
    if not service:
        sys.exit(1)

    try:
        message = build_message(to, subject, body, thread_id=thread_id, in_reply_to=in_reply_to)
        service.users().messages().send(userId="me", body=message).execute()
        logger.info(f"✅ Email sent successfully to {to}")
        log_action(approval_path, "success", f"to={to}, subject={subject[:50]}")

        # Move approval file to Done
        done_path = VAULT_PATH / "Done" / approval_path.name
        approval_path.rename(done_path)
        logger.info(f"Approval file moved to Done/")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        log_action(approval_path, f"error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
