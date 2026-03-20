"""
post_linkedin.py — Posts an approved message to LinkedIn via Playwright.

Called by orchestrator when a LinkedIn approval file appears in /Approved/.
Uses LinkedIn Web (web.linkedin.com) with a saved session to post.

First-time setup:
    python actions/post_linkedin.py --setup
    (Opens a browser — log into LinkedIn — session saved to secrets/linkedin_session/)

Usage (internal — called by orchestrator):
    python actions/post_linkedin.py <path_to_approval_file>

The approval file must have frontmatter:
    type: approval_request
    action: post_linkedin
    post_text: "The post content to publish"
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PostLinkedIn] %(levelname)s: %(message)s",
)
logger = logging.getLogger("PostLinkedIn")

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
SESSION_PATH = Path(os.getenv("LINKEDIN_SESSION_PATH", "secrets/linkedin_session"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"


def parse_frontmatter(file_path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter and return (fields, body)."""
    content = file_path.read_text(encoding="utf-8")
    fields = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    fields[key.strip()] = value.strip()
            body = parts[2].strip()
    return fields, body


def log_action(approval_file: Path, result: str, details: str = ""):
    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    entry = (
        f"\n### {datetime.now().strftime('%H:%M:%S')} — linkedin_post\n"
        f"- **approval_file:** {approval_file.name}\n"
        f"- **result:** {result}\n"
        f"- **dry_run:** {DRY_RUN}\n"
    )
    if details:
        entry += f"- **details:** {details}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def setup_session():
    """Open a browser so the user can log into LinkedIn and save the session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    SESSION_PATH.mkdir(parents=True, exist_ok=True)
    # Remove stale lockfile that prevents Chrome from reusing the profile dir
    import subprocess as _sp
    lockfile = SESSION_PATH / "lockfile"
    if lockfile.exists():
        # Only kill Playwright's own Chromium (ms-playwright path), never the user's Chrome
        playwright_chrome = str(Path.home() / "AppData/Local/ms-playwright")
        _sp.run(["powershell", "-Command",
                 f"Get-Process chrome -ErrorAction SilentlyContinue | "
                 f"Where-Object {{$_.Path -like '*ms-playwright*'}} | Stop-Process -Force; "
                 f"Start-Sleep 1; Remove-Item '{lockfile}' -Force -ErrorAction SilentlyContinue"],
                capture_output=True)
        logger.info("Removed stale lockfile.")
    logger.info("Opening browser — log into LinkedIn. Close the browser when done.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(SESSION_PATH),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        logger.info("Browser opened. Log in and then press Ctrl+C here.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        try:
            context.close()
        except Exception:
            pass  # Browser was already closed by user — session is saved

    logger.info("Session saved to: %s", SESSION_PATH)
    logger.info("You can now run the post script with an approval file.")


def post_to_linkedin(post_text: str) -> bool:
    """Post text to LinkedIn using saved Playwright session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    if not SESSION_PATH.exists():
        logger.error(f"LinkedIn session not found at {SESSION_PATH}. Run: python actions/post_linkedin.py --setup")
        return False

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(SESSION_PATH),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.new_page()

        try:
            # Navigate with shareActive=true — modern LinkedIn opens the post composer directly
            logger.info("Navigating to LinkedIn post composer...")
            page.goto("https://www.linkedin.com/feed/?shareActive=true", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            time.sleep(4)  # let feed + modal settle

            # Check if still logged in
            if "login" in page.url:
                logger.error("LinkedIn session expired. Run: python actions/post_linkedin.py --setup")
                context.close()
                return False

            # Editor selectors — try these first (shareActive=true may have opened the modal)
            editor_selectors = [
                ".ql-editor",
                "div[role='textbox']",
                "[contenteditable='true']",
                ".editor-content div",
                "div.share-creation-state__text-editor [contenteditable]",
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    page.wait_for_selector(selector, timeout=6000)
                    editor = page.locator(selector).first
                    logger.info(f"Post composer opened automatically — editor via: {selector!r}")
                    break
                except Exception:
                    continue

            # Fallback: click the "Start a post" trigger if modal didn't open automatically
            if not editor:
                logger.info("Modal not auto-opened — clicking 'Start a post'...")
                started = False
                start_selectors = [
                    ("get_by_role",        ("button", "Start a post")),
                    ("get_by_placeholder", "Start a post"),
                    ("get_by_text",        "Start a post"),
                    ("css", "button.share-box-feed-entry__trigger"),
                    ("css", ".share-box-feed-entry__trigger"),
                    ("css", "[data-control-name='share.sharebox_feed_create_update']"),
                    ("css", "div.share-box-feed-entry__top-bar"),
                    ("css", "[placeholder='Start a post']"),
                    ("css", "[aria-placeholder='Start a post']"),
                    # broad fallback: any clickable element whose text includes the phrase
                    ("css", "div[class*='share']:not([class*='social'])"),
                ]
                for kind, value in start_selectors:
                    try:
                        if kind == "get_by_role":
                            loc = page.get_by_role(value[0], name=value[1])
                        elif kind == "get_by_placeholder":
                            loc = page.get_by_placeholder(value)
                        elif kind == "get_by_text":
                            loc = page.get_by_text(value, exact=False)
                        else:
                            loc = page.locator(value)
                        loc.first.click(timeout=5000)
                        started = True
                        logger.info(f"Clicked start-post trigger via: {kind}={value!r}")
                        break
                    except Exception:
                        continue

                if not started:
                    raise Exception("Could not open post composer — LinkedIn UI may have changed.")

                time.sleep(2)
                for selector in editor_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=8000)
                        editor = page.locator(selector).first
                        logger.info(f"Found editor via: {selector!r}")
                        break
                    except Exception:
                        continue

            if not editor:
                raise Exception("Post editor not found.")

            editor.click()
            page.keyboard.type(post_text)
            time.sleep(2)

            # Click Post / Share button
            logger.info("Submitting post...")
            posted = False
            post_selectors = [
                ("get_by_role", ("button", "Post")),
                ("css", "button.share-actions__primary-action"),
                ("css", "[data-control-name='share.post']"),
                ("get_by_text", "Post"),
            ]
            for kind, value in post_selectors:
                try:
                    if kind == "get_by_role":
                        loc = page.get_by_role(value[0], name=value[1])
                    elif kind == "get_by_text":
                        loc = page.get_by_text(value, exact=True)
                    else:
                        loc = page.locator(value)
                    loc.first.click(timeout=5000)
                    posted = True
                    logger.info(f"Clicked post button via: {kind}={value!r}")
                    break
                except Exception:
                    continue
            if not posted:
                raise Exception("Could not find Post/Share button.")

            page.wait_for_timeout(4000)
            logger.info("LinkedIn post published successfully.")
            context.close()
            return True

        except Exception as e:
            logger.error(f"Playwright error: {e}")
            try:
                page.screenshot(path="secrets/linkedin_error.png")
                logger.info("Screenshot saved to secrets/linkedin_error.png")
            except Exception:
                pass
            context.close()
            return False


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--setup":
        setup_session()
        return

    if len(sys.argv) < 2:
        logger.error("Usage: python actions/post_linkedin.py <approval_file_path>")
        logger.error("       python actions/post_linkedin.py --setup  (first-time session setup)")
        sys.exit(1)

    approval_path = Path(sys.argv[1])
    if not approval_path.exists():
        logger.error(f"Approval file not found: {approval_path}")
        sys.exit(1)

    fields, body = parse_frontmatter(approval_path)

    if fields.get("action") != "post_linkedin":
        logger.error(f"Wrong action type: {fields.get('action')}. Expected 'post_linkedin'.")
        sys.exit(1)

    # Get post text from frontmatter or body
    post_text = fields.get("post_text", "").strip()
    if not post_text:
        # Extract from body — look for ## Post Content section
        lines = body.splitlines()
        capture = False
        captured = []
        for line in lines:
            if "## Post Content" in line:
                capture = True
                continue
            if capture:
                if line.startswith("##"):
                    break
                captured.append(line)
        post_text = "\n".join(captured).strip()

    if not post_text:
        logger.error("No post_text found in approval file.")
        sys.exit(1)

    logger.info(f"Post preview: {post_text[:100]}...")

    if DRY_RUN:
        logger.info("[DRY RUN] Would post to LinkedIn:")
        logger.info(f"[DRY RUN] {post_text}")
        log_action(approval_path, "dry_run_skipped")
        return

    success = post_to_linkedin(post_text)

    if success:
        log_action(approval_path, "success", post_text[:80])
        done_path = VAULT_PATH / "Done" / approval_path.name
        if done_path.exists():
            done_path.unlink()  # remove stale copy so rename succeeds on Windows
        approval_path.rename(done_path)
        logger.info("Approval file moved to Done/")
    else:
        log_action(approval_path, "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
