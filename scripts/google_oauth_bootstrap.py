#!/usr/bin/env python3
"""
Google OAuth Bootstrap Script — Phase 4.

One-time local script to obtain refresh tokens for Gmail and Calendar APIs.

Usage:
    1. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env (or environment).
    2. Run: uv run scripts/google_oauth_bootstrap.py
    3. Follow the browser OAuth consent flow.
    4. Copy the printed refresh_token into your .env as GMAIL_REFRESH_TOKEN
       and CALENDAR_REFRESH_TOKEN (they share the same token if both scopes
       were granted).

Scopes requested:
    - https://www.googleapis.com/auth/gmail.readonly
    - https://www.googleapis.com/auth/calendar.readonly
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("ERROR: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set.", file=sys.stderr)
        print("Add them to your .env file or export them in your shell.", file=sys.stderr)
        sys.exit(1)

    # Build the OAuth2 flow using the client config directly
    flow = InstalledAppFlow.from_client_config(
        client_config={
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    print("Opening browser for Google OAuth consent...")
    print(f"Scopes: {', '.join(SCOPES)}")
    print()

    try:
        creds = flow.run_local_server(port=8080)
    except Exception:
        # Fallback: print URL for manual copy
        auth_url, _ = flow.authorization_url(prompt="consent")
        print()
        print("=" * 60)
        print("Could not open browser automatically.")
        print()
        print("Open this URL in your browser:")
        print(auth_url)
        print()
        print("After authorizing, copy the 'code' parameter from the")
        print("redirect URL and paste it here:")
        code = input("Code: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    print()
    print("=" * 60)
    print("OAuth flow complete!")
    print()
    print(f"Refresh token: {creds.refresh_token}")
    print()
    print("Add this to your .env file:")
    print(f"  GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print(f"  CALENDAR_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
