"""Create a local .env from .env.example with strong random secrets.

Usage (repository root):
    python infra/docker/generate_env.py            # refuses to overwrite an existing .env
    python infra/docker/generate_env.py --force    # overwrite (old secrets are lost)

Every value that starts with "change-me" is replaced by a random URL-safe secret.
Secrets are written only to .env (git-ignored) and are never printed.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / ".env.example"
TARGET = REPO_ROOT / ".env"

PLACEHOLDER = re.compile(r"^(?P<key>[A-Z0-9_]+)=change-me[^\s#]*(?P<rest>.*)$")
# Keys whose secret must stay simple (used inside URLs).
URL_SAFE_ALNUM = {"REDIS_PASSWORD", "S3_ACCESS_KEY"}


FERNET_KEYS = {"AZINCO_MFA_ENCRYPTION_KEY"}


def new_secret(key: str) -> str:
    if key in FERNET_KEYS:
        return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    if key in URL_SAFE_ALNUM:
        return secrets.token_hex(16)
    return secrets.token_urlsafe(32).replace("-", "A").replace("_", "B")


def render(example_text: str) -> tuple[str, int]:
    out_lines: list[str] = []
    replaced = 0
    secrets_by_key: dict[str, str] = {}
    for line in example_text.splitlines():
        match = PLACEHOLDER.match(line)
        if match:
            key = match.group("key")
            secrets_by_key[key] = new_secret(key)
            out_lines.append(f"{key}={secrets_by_key[key]}{match.group('rest')}")
            replaced += 1
        else:
            out_lines.append(line)
    text = "\n".join(out_lines) + "\n"
    # Keep REDIS_URL consistent with the generated REDIS_PASSWORD.
    if "REDIS_PASSWORD" in secrets_by_key:
        text = re.sub(
            r"^REDIS_URL=redis://:[^@]*@",
            f"REDIS_URL=redis://:{secrets_by_key['REDIS_PASSWORD']}@",
            text,
            flags=re.MULTILINE,
        )
    return text, replaced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite an existing .env")
    args = parser.parse_args(argv)
    if TARGET.exists() and not args.force:
        print(".env already exists - not overwritten (use --force).", file=sys.stderr)
        return 1
    text, count = render(EXAMPLE.read_text(encoding="utf-8"))
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.name} with {count} generated secrets (values not shown).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
