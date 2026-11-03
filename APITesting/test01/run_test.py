#!/usr/bin/env python3
"""Test script to invoke eTranslation API v2 using the implementation client.

Request specification:
- Text: "Validatore dei file turtle (.ttl)"
- Source language: IT (Italian)
- Target languages: EN, DE (English, German)
- Glossary: TSV containing the term "turtle" preserved across IT -> EN, DE
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add the 'implementation' folder to sys.path so we can import the client
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
IMPLEMENTATION_DIR = REPO_ROOT / "implementation"

if str(IMPLEMENTATION_DIR) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTATION_DIR))

try:
    from etranslation_client import (  # type: ignore[import-not-found]
        DEFAULT_BASE_URL,
        ETranslationClient,
        ETranslationError,
        inline_document,
    )
except ImportError as exc:
    sys.exit(f"Error importing etranslation_client from {IMPLEMENTATION_DIR}: {exc}")

DEFAULT_TEXT = "Validatore dei file turtle (.ttl)"
DEFAULT_SOURCE = "IT"
DEFAULT_TARGETS = ["EN", "DE"]
DEFAULT_GLOSSARY_PATH = CURRENT_DIR / "glossary.tsv"


def find_config_path(cli_path: str | None) -> Path | None:
    """Find the configuration file path."""
    if cli_path:
        p = Path(cli_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Config file not found at: {cli_path}")

    # Check local config.json in test01
    local_config = CURRENT_DIR / "config.json"
    if local_config.is_file():
        return local_config

    # Check sibling test configs
    for sibling in ("test00", "test02", "test03"):
        sib_config = CURRENT_DIR.parent / sibling / "config.json"
        if sib_config.is_file():
            return sib_config

    # Check config.json in implementation/
    impl_config = IMPLEMENTATION_DIR / "config.json"
    if impl_config.is_file():
        return impl_config

    return None


def get_credentials(cli_config: str | None) -> tuple[str, str] | None:
    """Retrieve username and password from config file or environment variables."""
    config_file = find_config_path(cli_config)
    if config_file:
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            username = data.get("username")
            password = data.get("password")
            if username and password:
                return username, password
        except Exception as exc:
            print(f"Warning: Failed to parse config file {config_file}: {exc}", file=sys.stderr)

    env_user = os.getenv("ETRANSLATION_USERNAME")
    env_pass = os.getenv("ETRANSLATION_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass

    return None


def build_glossary_source(glossary_path: Path) -> dict[str, Any]:
    """Read glossary file and return an inline document file source."""
    if not glossary_path.is_file():
        raise FileNotFoundError(f"Glossary file not found: {glossary_path}")

    raw_bytes = glossary_path.read_bytes()
    fmt = glossary_path.suffix.lstrip(".").lower() or "tsv"
    return inline_document(raw_bytes, fmt, filename=glossary_path.name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run test01: eTranslation API call with text and glossary."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file containing username and password.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=DEFAULT_TEXT,
        help=f"Text snippet to translate (default: '{DEFAULT_TEXT}')",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=DEFAULT_SOURCE,
        help=f"Source language code (default: '{DEFAULT_SOURCE}')",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=DEFAULT_TARGETS,
        help=f"Target language codes (default: {DEFAULT_TARGETS})",
    )
    parser.add_argument(
        "--glossary",
        type=Path,
        default=DEFAULT_GLOSSARY_PATH,
        help=f"Path to glossary file (default: '{DEFAULT_GLOSSARY_PATH}')",
    )
    parser.add_argument(
        "--callback-url",
        type=str,
        default=None,
        help="Optional HTTP URL to receive the success callback notification.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload and simulated request without contacting the eTranslation API.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("eTranslation Test 01 - Text Translation with Glossary")
    print("=" * 70)
    print(f"Text to translate : {args.text}")
    print(f"Source language   : {args.source}")
    print(f"Target languages  : {args.targets}")
    print(f"Glossary file     : {args.glossary}")

    glossary_source = build_glossary_source(args.glossary)
    glossary_raw = base64.b64decode(glossary_source["document"]["content"]).decode("utf-8", errors="replace")
    print(f"Glossary content  :\n---\n{glossary_raw.strip()}\n---")

    notifications = None
    if args.callback_url:
        notifications = {
            "success": {"http": args.callback_url},
            "failure": {"http": args.callback_url},
        }
        print(f"Callback URL      : {args.callback_url}")

    if args.dry_run:
        print("\n[DRY RUN MODE] The following payload would be submitted to /askTranslate:")
        payload = {
            "textToTranslate": args.text,
            "sourceLanguage": args.source,
            "targetLanguages": args.targets,
            "glossary": glossary_source,
        }
        if notifications:
            payload["notifications"] = notifications
        print(json.dumps(payload, indent=2))
        print("\nDry run completed successfully.")
        return

    creds = get_credentials(args.config)
    if not creds:
        print("\n[!] No credentials found.", file=sys.stderr)
        print("    Please provide credentials by either:", file=sys.stderr)
        print(f"    1. Creating {CURRENT_DIR / 'config.json'} or {IMPLEMENTATION_DIR / 'config.json'}", file=sys.stderr)
        print("       (copy from config.example.json)", file=sys.stderr)
        print("    2. Setting environment variables ETRANSLATION_USERNAME and ETRANSLATION_PASSWORD", file=sys.stderr)
        print("    3. Or running with --dry-run to test payload generation without calling the API.", file=sys.stderr)
        sys.exit(1)

    username, password = creds
    print(f"\nConnecting to eTranslation API ({DEFAULT_BASE_URL}) as application: '{username}'...")

    try:
        with ETranslationClient(application=username, password=password) as client:
            status = client.get_status()
            print(f"Service status    : level {status.get('level')} ({status.get('message')})")

            print("Submitting translation request...")
            request_id = client.translate_text(
                source_language=args.source,
                target_languages=args.targets,
                text=args.text,
                glossary=glossary_source,
                notifications=notifications,
            )
            print(f"\n[SUCCESS] Request accepted! Request ID: {request_id}")
            if not notifications:
                print("Note: Since no callback URL was provided, translated text will be delivered")
                print("      to your registered notification endpoint (if configured on backend)")
                print("      or you can provide --callback-url to receive it via HTTP callback.")
    except ETranslationError as err:
        print(f"\n[ERROR] eTranslation rejected request (Code {err.error_code}): {err.error_message}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"\n[ERROR] Request failed: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
