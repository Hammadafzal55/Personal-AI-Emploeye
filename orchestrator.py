"""
orchestrator.py — Silver Tier Orchestrator for the Personal AI Employee.

This script manages four concurrent responsibilities:
  1. Filesystem Watcher  — detects files dropped in /Inbox
  2. Gmail Watcher       — polls Gmail for new important emails (if configured)
  3. /Approved/ Watcher  — detects human approvals and executes actions
  4. Scheduler           — runs time-based jobs (daily briefing, weekly CEO report)
  5. Needs_Action Poll   — triggers Claude when tasks are queued

Usage:
    python orchestrator.py

Environment variables (set in .env):
    VAULT_PATH              — path to AI_Employee_Vault (default: AI_Employee_Vault)
    CLAUDE_INTERVAL         — seconds between Needs_Action polls (default: 120)
    DRY_RUN                 — true = log only, don't call Claude/Gmail/LinkedIn
    GMAIL_TOKEN_PATH        — path to Gmail OAuth token (enables Gmail Watcher)
    GMAIL_CREDENTIALS_PATH  — path to Gmail credentials.json
    DAILY_BRIEFING_TIME     — HH:MM for daily briefing (default: 08:00)
    WEEKLY_BRIEFING_DAY     — weekday for CEO briefing 0=Mon…6=Sun (default: 0)

Requirements:
    pip install watchdog python-dotenv schedule
    pip install google-auth google-auth-oauthlib google-api-python-client  (for Gmail)
    pip install playwright && playwright install chromium                   (for LinkedIn)
"""

import os
import sys
import time
import shutil
import logging
import threading
import subprocess
import queue
from pathlib import Path
from datetime import datetime

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH             = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault")).resolve()
NEEDS_ACTION_PATH      = VAULT_PATH / "Needs_Action"
PENDING_APPROVAL_PATH  = VAULT_PATH / "Pending_Approval"
APPROVED_PATH          = VAULT_PATH / "Pending_Approval" / "Approved"
REJECTED_PATH          = VAULT_PATH / "Pending_Approval" / "Rejected"
CANCELLED_PATH         = VAULT_PATH / "Pending_Approval" / "Cancelled"
LOGS_PATH              = VAULT_PATH / "Logs"
DASHBOARD_PATH         = VAULT_PATH / "Dashboard.md"

# Queue for interactive approval prompts
approval_queue: queue.Queue = queue.Queue()
_queued_approval_names: set = set()  # dedup tracker
_approval_active = threading.Event()  # set while stdin_handler is mid-approval decision
_linkedin_lock = threading.Lock()    # serialise LinkedIn posts — one Chrome at a time
_claude_lock = threading.Lock()      # only one Claude subprocess at a time

CLAUDE_INTERVAL        = int(os.getenv("CLAUDE_INTERVAL", "120"))
DRY_RUN                = os.getenv("DRY_RUN", "true").lower() == "true"
DAILY_BRIEFING_TIME    = os.getenv("DAILY_BRIEFING_TIME", "08:00")
WEEKLY_BRIEFING_DAY    = int(os.getenv("WEEKLY_BRIEFING_DAY", "0"))  # 0 = Monday

GMAIL_TOKEN_PATH       = Path(os.getenv("GMAIL_TOKEN_PATH", "secrets/gmail_token.json"))
GMAIL_ENABLED          = GMAIL_TOKEN_PATH.exists()

LINKEDIN_SESSION_PATH  = Path(os.getenv("LINKEDIN_SESSION_PATH", "secrets/linkedin_session"))
LINKEDIN_ENABLED       = LINKEDIN_SESSION_PATH.exists()

# ---------------------------------------------------------------------------
# Prompts for Claude
# ---------------------------------------------------------------------------

def make_process_prompt() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        "Read AI_Employee_Vault/Company_Handbook.md for your rules. "
        "Then process all .md files in AI_Employee_Vault/Needs_Action/ "
        "(skip README.md). For each file: understand the task, create a "
        "Plan_*.md in AI_Employee_Vault/Plans/ if the task has multiple steps, "
        "execute safe actions immediately, write approval requests to "
        "AI_Employee_Vault/Pending_Approval/ for sensitive actions. "
        "IMPORTANT: After writing an approval request to /Pending_Approval/, "
        "IMMEDIATELY move the original source file (e.g. EMAIL_*.md) to "
        "AI_Employee_Vault/Done/ with 'status: pending_approval' — do NOT leave it "
        "in /Needs_Action/, otherwise it will be processed again on the next cycle. "
        "For files that required no approval: change status to 'done', tick checkboxes, "
        "append a '## Resolution' section, then move to AI_Employee_Vault/Done/. "
        "For EMAIL_*.md files, use the draft-email-reply skill. "
        f"Finally, update AI_Employee_Vault/Dashboard.md and append entries to AI_Employee_Vault/Logs/{today}.md. "
        "When updating Dashboard.md: "
        "(1) Update the 'last_updated' frontmatter timestamp. "
        "(2) Update System Status — if Gmail emails exist in /Done/ or /Needs_Action/, mark Gmail Watcher as '✅ Active'; "
        "if secrets/linkedin_session/ folder exists, mark LinkedIn Poster as '✅ Active'. "
        "(3) Update Inbox Summary counts to reflect actual current file counts. "
        "(4) Add a new row to Recent Activity (newest first). Keep at most 10 rows — remove oldest rows beyond 10. "
        "(5) Update Weekly Snapshot numbers (Tasks Completed, Approvals Pending). "
        "(6) Update Active Plans list."
    )

DAILY_BRIEFING_PROMPT = (
    "Read AI_Employee_Vault/Company_Handbook.md and AI_Employee_Vault/Business_Goals.md. "
    "Then write a concise daily briefing to "
    "AI_Employee_Vault/Briefings/DAILY_<today_date>.md that covers: "
    "(1) items pending in Needs_Action, "
    "(2) items awaiting approval in Pending_Approval, "
    "(3) any upcoming deadlines from Business_Goals.md, "
    "(4) one proactive suggestion. "
    "Then update AI_Employee_Vault/Dashboard.md: "
    "(1) Update 'last_updated' timestamp. "
    "(2) Update System Status — check secrets/linkedin_session/ exists → LinkedIn '✅ Active'; "
    "check secrets/gmail_token.json exists → Gmail Watcher '✅ Active'. "
    "(3) Update Inbox Summary counts. "
    "(4) Add briefing link to Weekly Snapshot 'Daily Briefing' row. "
    "(5) Add a Recent Activity row for the briefing. Keep at most 10 rows in Recent Activity — remove oldest beyond 10."
)

WEEKLY_CEO_PROMPT = (
    "Run the weekly-ceo-briefing skill. "
    "Read AI_Employee_Vault/Business_Goals.md, scan AI_Employee_Vault/Done/ for "
    "the past 7 days, audit AI_Employee_Vault/Logs/ for patterns, and write the "
    "Monday Morning CEO Briefing to AI_Employee_Vault/Briefings/. "
    "Update Dashboard.md when done."
)

PROCESS_APPROVALS_PROMPT = (
    "Run the process-approvals skill. "
    "Check AI_Employee_Vault/Pending_Approval/Approved/ for new approval files. "
    "For send_email actions: use the gmail MCP send_email tool (NOT any Python script). "
    "For post_linkedin actions: run actions/post_linkedin.py. "
    "Update the related task status, log results, and update Dashboard.md."
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orchestrator] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Orchestrator")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def pending_items() -> list[Path]:
    if not NEEDS_ACTION_PATH.exists():
        return []
    return [f for f in NEEDS_ACTION_PATH.glob("*.md") if f.name != "README.md"]


def approved_items() -> list[Path]:
    if not APPROVED_PATH.exists():
        return []
    return [f for f in APPROVED_PATH.glob("*.md") if f.name != "README.md"]


def find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        for name in ("claude.cmd", "claude"):
            candidate = Path(appdata) / "npm" / name
            if candidate.exists():
                return str(candidate)
    for extra in [Path.home() / "AppData" / "Roaming" / "npm", Path("/usr/local/bin"), Path("/usr/bin")]:
        for name in ("claude.cmd", "claude"):
            candidate = extra / name
            if candidate.exists():
                return str(candidate)
    return None


def build_subprocess_env() -> dict:
    env = os.environ.copy()
    appdata = env.get("APPDATA", "")
    if appdata:
        npm_bin = str(Path(appdata) / "npm")
        if npm_bin not in env.get("PATH", ""):
            env["PATH"] = npm_bin + os.pathsep + env.get("PATH", "")
    return env


def run_claude(prompt: str, label: str = "claude") -> bool:
    """Run Claude Code with a prompt. Returns True on success.

    Only one Claude subprocess runs at a time (guarded by _claude_lock).
    If Claude is already running the call returns False immediately.
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would trigger Claude for: {label}")
        return True

    if not _claude_lock.acquire(blocking=False):
        logger.info(f"Claude already running — skipping '{label}' (will retry next cycle)")
        return False

    try:
        claude_exe = find_claude()
        if not claude_exe:
            logger.error("Claude Code not found. Install: npm install -g @anthropic/claude-code")
            return False

        logger.info(f"Triggering Claude ({label})...")
        try:
            result = subprocess.run(
                [claude_exe, "--print", "--dangerously-skip-permissions", prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                env=build_subprocess_env(),
            )
            if result.returncode == 0:
                logger.info(f"Claude [{label}] completed successfully.")
                if result.stdout and result.stdout.strip():
                    logger.info(f"Output: {result.stdout.strip()[:200]}")
                return True
            else:
                logger.error(f"Claude [{label}] failed (code {result.returncode}): {(result.stderr or '')[:200]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"Claude [{label}] timed out after 10 minutes.")
            return False
    finally:
        _claude_lock.release()


def append_log(action_type: str, details: dict):
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_PATH / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    entry = (
        f"\n### {datetime.now().strftime('%H:%M:%S')} — {action_type}\n"
        + "\n".join(f"- **{k}:** {v}" for k, v in details.items())
        + "\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def _pipe_process_logs(proc: "subprocess.Popen", label: str):
    """Read stdout from a long-running subprocess and re-emit lines through the orchestrator logger.

    Runs in a daemon thread. While an approval prompt is active (_approval_active is set),
    lines are buffered and flushed only after the approval is resolved — keeping the terminal clean.
    """
    buffered: list[str] = []
    try:
        for line in iter(proc.stdout.readline, ""):
            stripped = line.rstrip()
            if not stripped:
                continue
            if _approval_active.is_set():
                buffered.append(stripped)
            else:
                # Flush any buffered lines first, then print the new one
                for b in buffered:
                    logger.info(f"[{label}] {b}")
                buffered.clear()
                logger.info(f"[{label}] {stripped}")
    except Exception:
        pass
    # Flush remaining lines on process exit
    for b in buffered:
        logger.info(f"[{label}] {b}")


# ---------------------------------------------------------------------------
# Approved/ watcher (HITL execution)
# ---------------------------------------------------------------------------

def _read_frontmatter_action(path: Path) -> str:
    """Return the 'action:' value from a frontmatter file, or empty string."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("action:"):
                return line.partition(":")[2].strip()
    except Exception:
        pass
    return ""


def _run_linkedin_serialised(script: Path, path: Path):
    """Run a LinkedIn post script while holding _linkedin_lock so only one Chrome runs at a time.

    stdout/stderr from the child process are captured and re-emitted through the
    orchestrator's logger so they appear in-order with the rest of the log output.
    """
    with _linkedin_lock:
        logger.info(f"LinkedIn: starting post for {path.name}")
        result = subprocess.run(
            [sys.executable, str(script), str(path)],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in (result.stdout or "").splitlines():
            if line.strip():
                logger.info(f"[LinkedIn] {line.strip()}")
        for line in (result.stderr or "").splitlines():
            if line.strip():
                logger.warning(f"[LinkedIn] {line.strip()}")
        if result.returncode != 0:
            logger.error(f"LinkedIn post failed for {path.name} (exit {result.returncode})")
        else:
            logger.info(f"LinkedIn: post completed for {path.name}")


def _dispatch_approved(path: Path):
    """Dispatch the correct executor for an approved file.

    send_email  → Claude (with gmail MCP server) processes the file using the
                  gmail.send_email MCP tool.  No Python script involved.
    post_linkedin → Python actions/post_linkedin.py (Playwright-based).
    unknown     → Fallback to Claude process-approvals skill.
    """
    action = _read_frontmatter_action(path)
    append_log("approval_dispatched", {"file": path.name, "action": action})

    if action == "send_email":
        # Use Claude + gmail MCP server — Claude calls the gmail.send_email tool
        logger.info(f"Dispatching send_email via gmail MCP for {path.name}")
        prompt = (
            "Run the process-approvals skill. "
            f"Process this single approved email file: {path}. "
            "Read the frontmatter (to, subject, thread_id, in_reply_to, body_file). "
            "Use the gmail MCP send_email tool to send the email. "
            "Move the approved file to AI_Employee_Vault/Done/ on success. "
            "Append a log entry to AI_Employee_Vault/Logs/ and update Dashboard.md."
        )
        threading.Thread(
            target=run_claude,
            args=(prompt, "send-email-mcp"),
            daemon=True,
        ).start()

    elif action == "post_linkedin":
        # LinkedIn: Python + Playwright, serialised so only one Chrome runs at a time
        script = Path(__file__).parent / "actions" / "post_linkedin.py"
        if script.exists():
            logger.info(f"Dispatching post_linkedin → {script.name} for {path.name}")
            threading.Thread(
                target=_run_linkedin_serialised,
                args=(script, path),
                daemon=True,
            ).start()
        else:
            logger.error(f"post_linkedin script not found: {script}")

    else:
        # Unknown action — fall back to Claude process-approvals skill
        logger.info(f"Unknown action '{action}' in {path.name} — falling back to Claude")
        threading.Thread(
            target=run_claude,
            args=(PROCESS_APPROVALS_PROMPT, "process-approvals"),
            daemon=True,
        ).start()


class ApprovedFolderHandler(FileSystemEventHandler):
    """When a file lands in /Approved/, dispatch to the correct action script directly."""

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".md" or path.name == "README.md":
            return
        time.sleep(0.5)  # let file finish writing
        _dispatch_approved(path)

    def on_moved(self, event):
        dest = Path(event.dest_path)
        if dest.parent.resolve() == APPROVED_PATH.resolve():
            self.on_created(type("E", (), {"is_directory": False, "src_path": str(dest)})())


def launch_approved_watcher() -> "Observer | None":
    if not WATCHDOG_AVAILABLE:
        logger.warning("watchdog not installed — /Approved/ watcher disabled.")
        return None
    APPROVED_PATH.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(ApprovedFolderHandler(), str(APPROVED_PATH), recursive=False)
    observer.start()
    logger.info(f"Approved/ Watcher started — watching: {APPROVED_PATH}")
    return observer


# ---------------------------------------------------------------------------
# Interactive approval system — watches /Pending_Approval/ and prompts user
# ---------------------------------------------------------------------------

class PendingApprovalHandler(FileSystemEventHandler):
    """Detects new approval requests written by Claude and queues them for review."""

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.parent.resolve() != PENDING_APPROVAL_PATH.resolve():
            return
        if path.suffix != ".md" or path.name == "README.md":
            return
        if path.name in _queued_approval_names:
            return  # already queued — skip duplicate
        time.sleep(0.5)  # let Claude finish writing
        _queued_approval_names.add(path.name)
        logger.info(f"New approval request queued: {path.name}")
        approval_queue.put(path)
        # Immediately notify so the user knows to press Enter to review
        print(f"\n  *** APPROVAL NEEDED: {path.name} — press Enter to review ***\n")


def _format_approval_display(path: Path) -> str:
    """Return a nicely formatted terminal display of an approval request."""
    SEP = "=" * 60
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        content = "(could not read file)"

    lines = [
        "",
        SEP,
        f"  APPROVAL REQUIRED — {path.name}",
        SEP,
        content,
        SEP,
    ]
    return "\n".join(lines)


def _do_approve(path: Path):
    """Move an approval file to /Approved/ and dispatch the action."""
    dest = APPROVED_PATH / path.name
    try:
        path.rename(dest)
        logger.info(f"APPROVED: {path.name} — moved to Approved/.")
        append_log("approval_granted", {"file": path.name})
        _dispatch_approved(dest)
    except FileNotFoundError:
        logger.warning(f"File already moved: {path.name} — skipping.")
    _queued_approval_names.discard(path.name)
    try:
        approval_queue.task_done()
    except Exception:
        pass
    if approval_queue.empty():
        _approval_active.clear()


def _do_reject(path: Path):
    """Move an approval file to /Cancelled/."""
    dest = CANCELLED_PATH / path.name
    try:
        path.rename(dest)
        logger.info(f"REJECTED: {path.name} — moved to Cancelled/.")
        append_log("approval_rejected", {"file": path.name})
    except FileNotFoundError:
        logger.warning(f"File already moved: {path.name} — skipping.")
    _queued_approval_names.discard(path.name)
    try:
        approval_queue.task_done()
    except Exception:
        pass
    if approval_queue.empty():
        _approval_active.clear()


def _try_dequeue_approval() -> "Path | None":
    """Dequeue the next pending approval if one exists, else return None."""
    try:
        path = approval_queue.get_nowait()
        if not path.exists():
            try:
                approval_queue.task_done()
            except Exception:
                pass
            return None
        _approval_active.set()
        return path
    except queue.Empty:
        return None


def _rescan_pending_approvals():
    """Immediately queue any approval files in /Pending_Approval/ not yet queued.

    Called after every Claude run so approvals are in the queue before the user
    could type A/R, eliminating the watchdog-delay race condition.
    """
    for f in sorted(PENDING_APPROVAL_PATH.glob("*.md")):
        if f.parent.resolve() != PENDING_APPROVAL_PATH.resolve():
            continue
        if f.name == "README.md":
            continue
        if f.name not in _queued_approval_names:
            _queued_approval_names.add(f.name)
            logger.info(f"Post-Claude scan: queued new approval request: {f.name}")
            approval_queue.put(f)
            print(f"\n  *** APPROVAL NEEDED: {f.name} — press Enter to review ***\n")


def _handle_startup_approvals():
    """Synchronously process any approval files left from a previous run.

    Called in the main thread BEFORE watchers and the scheduler are started, so
    the user sees a clean prompt with zero interleaving output.
    """
    CANCELLED_PATH.mkdir(parents=True, exist_ok=True)
    APPROVED_PATH.mkdir(parents=True, exist_ok=True)

    existing = sorted(
        f for f in PENDING_APPROVAL_PATH.glob("*.md")
        if f.parent.resolve() == PENDING_APPROVAL_PATH.resolve() and f.name != "README.md"
    )
    if not existing:
        return

    logger.info(f"Found {len(existing)} pending approval(s) — handling before startup.")
    for path in existing:
        _queued_approval_names.add(path.name)
        print(_format_approval_display(path))
        print("\n  [A] Approve  |  [R] Reject\n")
        while True:
            try:
                line = input("  Decision [A/R] > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if line in ("a", "approve", "y", "yes"):
                dest = APPROVED_PATH / path.name
                try:
                    path.rename(dest)
                    logger.info(f"APPROVED: {path.name} — moved to Approved/.")
                    append_log("approval_granted", {"file": path.name})
                    _dispatch_approved(dest)
                except FileNotFoundError:
                    logger.warning(f"File already moved: {path.name}")
                break
            elif line in ("r", "reject", "n", "no"):
                dest = CANCELLED_PATH / path.name
                try:
                    path.rename(dest)
                    logger.info(f"REJECTED: {path.name} — moved to Cancelled/.")
                    append_log("approval_rejected", {"file": path.name})
                except FileNotFoundError:
                    logger.warning(f"File already moved: {path.name}")
                break
            else:
                print("  Please type A to approve or R to reject.")
    print()  # blank line after last approval before startup logs resume


def stdin_handler():
    """Single thread that owns stdin — handles both approval prompts and manual commands.

    Priority: if an approval is pending, show it and wait for A/R before accepting commands.
    If the user types A/R while in command mode, check whether a new approval just arrived
    and process it immediately rather than saying 'Unknown command'.
    """
    def print_help():
        print("\n  Commands:  post | brief | ceo | process | help\n")

    current_approval: "Path | None" = None

    while True:
        # --- Check for a new approval to display ---
        if current_approval is None:
            pending = _try_dequeue_approval()
            if pending:
                current_approval = pending
                print(_format_approval_display(current_approval))
                print("\n  [A] Approve  |  [R] Reject\n")

        # --- Read one line from stdin ---
        try:
            if current_approval:
                line = input("  Decision [A/R] > ").strip().lower()
            else:
                line = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        # --- Route input ---
        if current_approval:
            if line in ("a", "approve", "y", "yes"):
                _do_approve(current_approval)
                current_approval = None
            elif line in ("r", "reject", "n", "no"):
                _do_reject(current_approval)
                current_approval = None
            else:
                print("  Please type A to approve or R to reject.")
        else:
            # Command mode — but first check: did the user type A/R because a new
            # approval just arrived (race between Claude writing the file and stdin_handler
            # displaying the prompt)?
            if line in ("a", "approve", "y", "yes", "r", "reject", "n", "no"):
                pending = _try_dequeue_approval()
                if not pending:
                    # Watchdog may still be in its 0.5s sleep — give it a moment then retry
                    time.sleep(1.5)
                    _rescan_pending_approvals()
                    pending = _try_dequeue_approval()
                if pending:
                    # Show the approval content so user can confirm what they just approved
                    print(_format_approval_display(pending))
                    if line in ("a", "approve", "y", "yes"):
                        _do_approve(pending)
                        print(f"  Approved: {pending.name}")
                    else:
                        _do_reject(pending)
                        print(f"  Rejected: {pending.name}")
                    current_approval = None
                    continue
                # No pending approval — unknown command
                print(f"  No pending approval found. Type 'help' for commands.")
            elif line == "post":
                print("  Drafting LinkedIn post...")
                threading.Thread(target=run_linkedin_post_draft, daemon=True).start()
            elif line == "brief":
                print("  Running daily briefing...")
                threading.Thread(target=run_daily_briefing, daemon=True).start()
            elif line == "ceo":
                print("  Running CEO briefing...")
                threading.Thread(target=run_weekly_ceo_briefing, daemon=True).start()
            elif line == "process":
                items = pending_items()
                if items:
                    print(f"  Processing {len(items)} item(s)...")
                    threading.Thread(
                        target=run_claude,
                        args=(make_process_prompt(), "process-inbox-tasks"),
                        daemon=True,
                    ).start()
                else:
                    print("  Needs_Action is empty.")
            elif line == "help":
                print_help()
            elif line:
                print(f"  Unknown command: '{line}'. Type 'help'.")


def launch_pending_approval_watcher() -> "Observer | None":
    if not WATCHDOG_AVAILABLE:
        return None
    PENDING_APPROVAL_PATH.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(PendingApprovalHandler(), str(PENDING_APPROVAL_PATH), recursive=False)
    observer.start()
    logger.info(f"Pending Approval Watcher started — watching: {PENDING_APPROVAL_PATH}")
    return observer


# ---------------------------------------------------------------------------
# Filesystem watcher (Inbox)
# ---------------------------------------------------------------------------

def launch_filesystem_watcher() -> "subprocess.Popen | None":
    watcher_script = Path(__file__).parent / "watchers" / "filesystem_watcher.py"
    if not watcher_script.exists():
        logger.warning(f"Filesystem watcher not found: {watcher_script}")
        return None
    env = os.environ.copy()
    env["VAULT_PATH"] = str(VAULT_PATH)
    proc = subprocess.Popen(
        [sys.executable, str(watcher_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    logger.info(f"Filesystem Watcher started (PID {proc.pid})")
    threading.Thread(target=_pipe_process_logs, args=(proc, "FsWatcher"), daemon=True).start()
    return proc


# ---------------------------------------------------------------------------
# Gmail watcher
# ---------------------------------------------------------------------------

def launch_gmail_watcher() -> "subprocess.Popen | None":
    if not GMAIL_ENABLED:
        logger.info("Gmail Watcher disabled — no token found at secrets/gmail_token.json")
        logger.info("  To enable: python setup/gmail_oauth_setup.py")
        return None

    watcher_script = Path(__file__).parent / "watchers" / "gmail_watcher.py"
    if not watcher_script.exists():
        logger.warning(f"Gmail watcher not found: {watcher_script}")
        return None

    env = os.environ.copy()
    env["VAULT_PATH"] = str(VAULT_PATH)
    proc = subprocess.Popen(
        [sys.executable, str(watcher_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    logger.info(f"Gmail Watcher started (PID {proc.pid})")
    threading.Thread(target=_pipe_process_logs, args=(proc, "GmailWatcher"), daemon=True).start()
    return proc


# ---------------------------------------------------------------------------
# Scheduler (daily briefing + weekly CEO report)
# ---------------------------------------------------------------------------

def run_daily_briefing():
    logger.info("Scheduler: running daily briefing...")
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = DAILY_BRIEFING_PROMPT.replace("<today_date>", today)
    run_claude(prompt, label="daily-briefing")
    append_log("scheduled_daily_briefing", {"time": datetime.now().isoformat()})


def run_weekly_ceo_briefing():
    logger.info("Scheduler: running weekly CEO briefing...")
    run_claude(WEEKLY_CEO_PROMPT, label="weekly-ceo-briefing")
    append_log("scheduled_weekly_ceo_briefing", {"time": datetime.now().isoformat()})


def run_linkedin_post_draft():
    logger.info("Scheduler: drafting LinkedIn post...")
    prompt = (
        "Run the draft-linkedin-post skill. "
        "Read AI_Employee_Vault/Business_Goals.md and AI_Employee_Vault/Company_Handbook.md. "
        "Draft a LinkedIn post that promotes the business and routes it to "
        "AI_Employee_Vault/Pending_Approval/ for human review."
    )
    run_claude(prompt, label="draft-linkedin-post")
    append_log("scheduled_linkedin_draft", {"time": datetime.now().isoformat()})


def run_done_cleanup():
    """Purge low-value files from /Done/ that are no longer needed.

    Keeps:
    - Personal contact emails (non-promotional, non-notification)
    - Action-required flagged emails
    - EMAIL_SEND_* records (sent email audit trail)
    - LINKEDIN_* posts (brand portfolio)
    - Plans, briefing references, QUESTION_*, REPLY_*
    - Files < 7 days old (grace period)

    Removes:
    - Promotional emails (CATEGORY_PROMOTIONS, known promo senders)
    - Notification-only emails (no reply needed, no action required)
    - Self-sent draft copies
    - Test/FILE_test_* artifacts
    - Old Plans/DRAFT_reply_* with no active pending approval
    """
    from datetime import timedelta

    PROMO_SENDERS = {
        "hello@students.udemy.com", "info@updates.lumosity.com",
        "noreply@unstop.com", "noreply@resume.io",
    }
    PROMO_SUBJECTS = {"promotion", "offer", "discount", "newsletter", "workout", "pi day"}
    PROMO_LABELS = {"category_promotions"}
    NOTIFICATION_ONLY_SUBJECTS = {"finish setting up", "ready for today"}
    CUTOFF = datetime.now() - timedelta(days=7)

    done_dir = VAULT_PATH / "Done"
    plans_dir = VAULT_PATH / "Plans"
    pending_dir = VAULT_PATH / "Pending_Approval"
    removed = []

    def _parse_fm(path: Path) -> dict:
        try:
            content = path.read_text(encoding="utf-8")
            fields = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            fields[k.strip().lower()] = v.strip().lower()
            return fields
        except Exception:
            return {}

    # --- Clean /Done/ ---
    for f in done_dir.glob("*.md"):
        if f.name == "README.md":
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
        except Exception:
            continue
        if mtime > CUTOFF:
            continue  # too recent — leave alone

        fm = _parse_fm(f)
        ftype = fm.get("type", "")
        fname_lower = f.name.lower()

        # Always keep these
        if any(fname_lower.startswith(p) for p in ("email_send_", "linkedin_", "reply_", "question_")):
            continue
        if ftype in ("plan", "status_report", "weekly_briefing", "daily_briefing"):
            continue

        # Remove test artifacts
        if fname_lower.startswith("file_test_"):
            f.unlink()
            removed.append(f.name)
            continue

        # Remove promotional / notification emails
        if ftype == "email":
            sender = fm.get("from", "")
            subject = fm.get("subject", "")
            labels = fm.get("labels", "")
            is_promo = (
                any(s in sender for s in PROMO_SENDERS)
                or any(p in subject for p in PROMO_SUBJECTS)
                or any(p in labels for p in PROMO_LABELS)
                or any(p in subject for p in NOTIFICATION_ONLY_SUBJECTS)
                or "category_promotions" in labels
                or fm.get("labels", "").count("sent") > 0 and "no subject" in subject
            )
            if is_promo:
                f.unlink()
                removed.append(f.name)

    # --- Clean /Plans/ stale drafts ---
    active_body_files = set()
    for pf in pending_dir.glob("*.md"):
        pf_fm = _parse_fm(pf)
        bf = pf_fm.get("body_file", "")
        if bf:
            active_body_files.add(Path(bf).name)

    for f in plans_dir.glob("DRAFT_reply_*.md"):
        if f.name in active_body_files:
            continue  # still referenced by a pending approval
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
        except Exception:
            continue
        if mtime <= CUTOFF:
            f.unlink()
            removed.append(f"Plans/{f.name}")

    if removed:
        logger.info(f"Done cleanup: removed {len(removed)} stale file(s): {removed}")
        append_log("done_cleanup", {"removed_count": len(removed), "files": ", ".join(removed)})
    else:
        logger.info("Done cleanup: nothing to remove.")


def _briefing_exists_today() -> bool:
    """Return True if a daily briefing file already exists for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    briefings = VAULT_PATH / "Briefings"
    return briefings.exists() and any(briefings.glob(f"DAILY_{today}*.md"))


def _linkedin_draft_exists_today() -> bool:
    """Return True if a LinkedIn draft or approval file was already created today."""
    today = datetime.now().strftime("%Y-%m-%d")
    pending = VAULT_PATH / "Pending_Approval"
    done = VAULT_PATH / "Done"
    return (
        any(pending.glob(f"LINKEDIN_*{today}*.md"))
        or any(done.glob(f"LINKEDIN_*{today}*.md"))
    )


def _past_time(hhmm: str) -> bool:
    """Return True if the current local time is past hh:mm today."""
    h, m = map(int, hhmm.split(":"))
    now = datetime.now()
    return (now.hour, now.minute) >= (h, m)


def _run_startup_catchup():
    """Run any scheduled jobs that were missed because the orchestrator started late."""
    now = datetime.now()

    # Daily briefing — run if past scheduled time and no briefing exists yet today
    if _past_time(DAILY_BRIEFING_TIME) and not _briefing_exists_today():
        logger.info(f"Startup catch-up: daily briefing was missed (past {DAILY_BRIEFING_TIME}) — running now.")
        threading.Thread(target=run_daily_briefing, daemon=True).start()

    # LinkedIn post draft — run if past 09:00 and no draft exists yet today
    if _past_time("09:00") and not _linkedin_draft_exists_today():
        logger.info("Startup catch-up: LinkedIn post draft was missed (past 09:00) — running now.")
        threading.Thread(target=run_linkedin_post_draft, daemon=True).start()

    # Weekly CEO briefing — run if it's the configured weekday, past 07:00, and no CEO briefing today
    if now.weekday() == WEEKLY_BRIEFING_DAY and _past_time("07:00"):
        briefings = VAULT_PATH / "Briefings"
        today = now.strftime("%Y-%m-%d")
        if briefings.exists() and not any(briefings.glob(f"*CEO*{today}*.md")) and not any(briefings.glob(f"*Monday*{today}*.md")):
            logger.info("Startup catch-up: weekly CEO briefing was missed — running now.")
            threading.Thread(target=run_weekly_ceo_briefing, daemon=True).start()

    # Done/ cleanup — run immediately on startup (always safe to run; it respects the 7-day grace period)
    threading.Thread(target=run_done_cleanup, daemon=True).start()


def start_scheduler():
    if not SCHEDULE_AVAILABLE:
        logger.warning("'schedule' library not installed — scheduler disabled.")
        logger.warning("  Install with: pip install schedule")
        return

    # Daily briefing at configured time
    schedule.every().day.at(DAILY_BRIEFING_TIME).do(run_daily_briefing)
    logger.info(f"Scheduled: daily briefing at {DAILY_BRIEFING_TIME}")

    # Weekly CEO briefing on configured day at 07:00
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_name = day_names[WEEKLY_BRIEFING_DAY]
    getattr(schedule.every(), day_name).at("07:00").do(run_weekly_ceo_briefing)
    logger.info(f"Scheduled: weekly CEO briefing every {day_name.capitalize()} at 07:00")

    # LinkedIn post draft: every day at 09:00
    schedule.every().day.at("09:00").do(run_linkedin_post_draft)
    logger.info("Scheduled: LinkedIn post draft every day at 09:00")

    # Done/ cleanup: every Sunday at 23:00
    schedule.every().sunday.at("23:00").do(run_done_cleanup)
    logger.info("Scheduled: Done/ cleanup every Sunday at 23:00")

    def scheduler_loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    thread = threading.Thread(target=scheduler_loop, daemon=True, name="Scheduler")
    thread.start()
    logger.info("Scheduler thread started.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("  Personal AI Employee — Silver Orchestrator")
    logger.info("=" * 60)
    logger.info(f"Vault:          {VAULT_PATH}")
    logger.info(f"Poll interval:  {CLAUDE_INTERVAL}s")
    logger.info(f"Dry run:        {DRY_RUN}")
    logger.info(f"Gmail watcher:  {'✅ enabled' if GMAIL_ENABLED else '❌ disabled (run gmail_oauth_setup.py)'}")
    logger.info(f"LinkedIn:       {'✅ session found' if LINKEDIN_ENABLED else '❌ disabled (run post_linkedin.py --setup)'}")
    logger.info(f"Daily briefing: {DAILY_BRIEFING_TIME}")
    if DRY_RUN:
        logger.info("NOTE: DRY_RUN=true — Claude/actions will NOT execute. Set DRY_RUN=false in .env.")
    logger.info("-" * 60)

    # Ensure all vault folders exist
    for folder in [
        "Needs_Action", "Done", "Plans", "Logs", "Inbox", "Briefings",
        "Pending_Approval", "Pending_Approval/Approved",
        "Pending_Approval/Rejected", "Pending_Approval/Cancelled",
    ]:
        (VAULT_PATH / folder).mkdir(parents=True, exist_ok=True)

    # Handle any approvals left from previous run BEFORE starting watchers.
    # This keeps the approval prompt clean — no watcher startup noise interleaving.
    _handle_startup_approvals()

    # Launch background processes and threads
    fs_watcher_proc      = launch_filesystem_watcher()
    gmail_watcher_proc   = launch_gmail_watcher()
    approved_observer    = launch_approved_watcher()
    pending_observer     = launch_pending_approval_watcher()
    start_scheduler()
    _run_startup_catchup()  # catch up on any jobs missed because orchestrator started late

    # Single stdin thread — handles both approval prompts and manual commands
    stdin_thread = threading.Thread(target=stdin_handler, daemon=True, name="StdinHandler")
    stdin_thread.start()
    logger.info("Ready — type 'post' to draft a LinkedIn post, 'help' for all commands.")

    # --- Main poll loop ---
    _last_approval_skip_count = -1  # suppress repeated "approval pending" log spam
    try:
        while True:
            items = pending_items()
            triggered = False

            # Don't trigger Claude while the user is mid-approval
            if _approval_active.is_set() or not approval_queue.empty():
                pending_count = approval_queue.qsize() + (1 if _approval_active.is_set() else 0)
                if pending_count != _last_approval_skip_count:
                    logger.info(
                        f"Approval pending ({pending_count} item(s)) — "
                        "skipping Claude trigger until approvals are resolved."
                    )
                    _last_approval_skip_count = pending_count
            elif items:
                _last_approval_skip_count = -1  # reset so next approval batch logs again
                logger.info(f"Found {len(items)} item(s) in Needs_Action: {[f.name for f in items]}")
                run_claude(make_process_prompt(), label="process-inbox-tasks")
                triggered = True
                # Immediately queue any approval files Claude just wrote — don't wait for watchdog
                _rescan_pending_approvals()
            else:
                _last_approval_skip_count = -1  # reset so next approval batch logs again
                logger.info("Needs_Action is empty — nothing to process.")

            append_log("orchestrator_heartbeat", {
                "needs_action": len(items),
                "approved_pending": len(approved_items()),
                "claude_triggered": "Yes" if triggered else "No",
                "dry_run": "Yes" if DRY_RUN else "No",
            })

            time.sleep(CLAUDE_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user.")
    finally:
        # Clean shutdown
        for obs in [approved_observer, pending_observer]:
            if obs:
                obs.stop()
                obs.join(timeout=3)
        for proc in [fs_watcher_proc, gmail_watcher_proc]:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
