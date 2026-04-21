#!/usr/bin/env python3
"""Generate a MusicKit developer token (JWT) for Apple Music API access.

Prerequisites:
  1. Apple Developer Program membership ($99/year)
  2. A MusicKit key from https://developer.apple.com/account/resources/authkeys/list
     - Download the .p8 file (AuthKey_XXXXXXXXXX.p8)
     - Note the Key ID and your Team ID

Usage:
  python3 pipeline/musickit_token.py

Environment variables (or prompted interactively):
  APPLE_TEAM_ID       — 10-char team ID from developer.apple.com
  MUSICKIT_KEY_ID     — 10-char key ID from the MusicKit key
  MUSICKIT_KEY_PATH   — path to the .p8 private key file

The generated token is valid for up to 6 months and should be stored as:
  - APPLE_MUSIC_TOKEN in GitHub Actions secrets (for the pipeline)
  - MUSICKIT_DEVELOPER_TOKEN in GitHub Actions secrets (for the Astro build)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    import jwt
except ImportError:
    print("PyJWT with crypto required: pip install 'PyJWT[crypto]'", file=sys.stderr)
    sys.exit(1)


def generate_musickit_token(
    team_id: str,
    key_id: str,
    private_key: str,
    expiry_days: int = 180,
) -> str:
    """Generate a MusicKit developer token (ES256 JWT).

    Args:
        team_id: Apple Developer Team ID (10 chars)
        key_id: MusicKit Key ID (10 chars)
        private_key: Contents of the .p8 private key file
        expiry_days: Token validity in days (max 180 = ~6 months)

    Returns:
        Signed JWT string
    """
    now = int(time.time())
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + (expiry_days * 24 * 60 * 60),
    }
    headers = {
        "alg": "ES256",
        "kid": key_id,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def _load_key(path: str) -> str:
    """Load a .p8 private key file."""
    key_path = Path(path).expanduser()
    if not key_path.exists():
        print(f"Key file not found: {key_path}", file=sys.stderr)
        sys.exit(1)
    return key_path.read_text().strip()


if __name__ == "__main__":
    team_id = os.environ.get("APPLE_TEAM_ID") or input("Apple Team ID: ").strip()
    key_id = os.environ.get("MUSICKIT_KEY_ID") or input("MusicKit Key ID: ").strip()
    key_path = os.environ.get("MUSICKIT_KEY_PATH") or input("Path to .p8 key file: ").strip()

    if not all([team_id, key_id, key_path]):
        print("All three values are required.", file=sys.stderr)
        sys.exit(1)

    private_key = _load_key(key_path)
    token = generate_musickit_token(team_id, key_id, private_key)

    print("\n" + "=" * 60)
    print("MusicKit developer token generated!")
    print("=" * 60)
    print(f"\nValid for 180 days (expires {time.strftime('%Y-%m-%d', time.localtime(time.time() + 180*86400))})")
    print(f"\nToken (first 50 chars): {token[:50]}...")
    print(f"\nFull token length: {len(token)} characters")
    print("\nAdd as GitHub Actions secrets:")
    print(f"  APPLE_MUSIC_TOKEN={token}")
    print(f"  MUSICKIT_DEVELOPER_TOKEN={token}")
    print("\nOr set in .env:")
    print(f"  APPLE_MUSIC_TOKEN={token}")
    print("=" * 60)
