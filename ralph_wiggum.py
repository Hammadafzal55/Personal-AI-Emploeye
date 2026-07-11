"""
ralph_wiggum.py - Claude Code Stop hook for the Personal AI Employee.

When Claude finishes a turn, this script runs. It checks whether tasks
are still pending in the vault and, if so, re-injects the original prompt
so Claude continues working autonomously (Gold tier file-movement strategy).

Exit codes:
    0 - allow stop (nothing pending or max iterations reached)
    2 - block stop and re-inject printed message as next user message
"""

import json
import os
import sys
from pathlib import Path

VAULT_PATH = Path(os.getenv("VAULT_PATH", "AI_Employee_Vault"))
NEEDS_ACTION_PATH = VAULT_PATH / "Needs_Action"
STATE_PATH = Path("secrets/ralph_state.json")


def load_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def delete_state():
    try:
        STATE_PATH.unlink()
    except FileNotFoundError:
        pass


def pending_md_files() -> list:
    """Return all .md files in Needs_Action except README.md."""
    if not NEEDS_ACTION_PATH.exists():
        return []
    return [f for f in NEEDS_ACTION_PATH.glob("*.md") if f.name != "README.md"]


def main():
    state = load_state()
    if state is None:
        sys.exit(0)  # No active task - allow Claude to stop

    prompt = state.get("prompt", "")
    iterations = state.get("iterations", 0)
    task_files = state.get("task_files", [])
    max_iterations = state.get("max_iterations", 10)

    # Max iterations guard - prevent infinite loops
    if iterations >= max_iterations:
        delete_state()
        sys.exit(0)

    original_still_pending = any(
        (NEEDS_ACTION_PATH / fname).exists() for fname in task_files
    )
    any_pending = bool(pending_md_files())

    if not original_still_pending and not any_pending:
        delete_state()
        sys.exit(0)

    iterations += 1
    state["iterations"] = iterations
    save_state(state)

    print(
        f"[Ralph Wiggum - Iteration {iterations}/{max_iterations}] "
        f"Tasks still pending in /Needs_Action. Continue working.\n\n{prompt}"
    )
    sys.exit(2)  # Block stop - stdout becomes next user message


if __name__ == "__main__":
    main()
