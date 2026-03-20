"""
gmail_oauth_setup.py — One-time OAuth flow to authorize Gmail access.

Run this ONCE to generate secrets/gmail_token.json.
After that, gmail_watcher.py will auto-refresh the token.

Steps:
    1. Go to console.cloud.google.com
    2. Create a project → Enable Gmail API
    3. Credentials → Create OAuth 2.0 Client ID (Desktop App)
    4. Download the JSON → save as secrets/gmail_credentials.json
    5. Run: python setup/gmail_oauth_setup.py
    6. A browser window will open → log in → grant permission
    7. Token saved to secrets/gmail_token.json

Usage:
    python setup/gmail_oauth_setup.py
"""

import os
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    print("ERROR: Google libraries not installed.")
    print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CREDENTIALS_PATH = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "secrets/gmail_credentials.json"))
TOKEN_PATH = Path(os.getenv("GMAIL_TOKEN_PATH", "secrets/gmail_token.json"))


def main():
    print("=" * 60)
    print("  Gmail OAuth Setup — Personal AI Employee")
    print("=" * 60)

    if not CREDENTIALS_PATH.exists():
        print(f"\nERROR: credentials.json not found at: {CREDENTIALS_PATH}")
        print("\nTo get credentials.json:")
        print("  1. Go to: console.cloud.google.com")
        print("  2. Create a project and enable the Gmail API")
        print("  3. Create OAuth 2.0 credentials (Desktop App)")
        print(f"  4. Download and save to: {CREDENTIALS_PATH}")
        sys.exit(1)

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            print("\nOpening browser for authorization...")
            print("Log in with the Gmail account you want the AI Employee to monitor.\n")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"\nToken saved to: {TOKEN_PATH}")
    print("\nYou can now run the Gmail Watcher:")
    print("  python watchers/gmail_watcher.py")
    print("  (or it will start automatically via orchestrator.py)")


if __name__ == "__main__":
    main()
