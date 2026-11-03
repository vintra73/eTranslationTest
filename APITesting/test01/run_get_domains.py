#!/usr/bin/env python3
"""Script to call the /getDomains endpoint of the eTranslation REST API v2 (Test 00).

Retrieves supported domains and language pairs (such as IT-EN, IT-DE).
"""

from __future__ import annotations

import argparse
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
    )
except ImportError as exc:
    sys.exit(f"Error importing etranslation_client from {IMPLEMENTATION_DIR}: {exc}")


def find_config_path(cli_path: str | None) -> Path | None:
    """Find configuration file path."""
    if cli_path:
        p = Path(cli_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Config file not found at: {cli_path}")

    # Check local config.json in test00
    local_config = CURRENT_DIR / "config.json"
    if local_config.is_file():
        return local_config

    # Check config.json in sibling test folders
    for sibling in ("test01", "test02"):
        sibling_config = CURRENT_DIR.parent / sibling / "config.json"
        if sibling_config.is_file():
            return sibling_config

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query the eTranslation API /getDomains endpoint for supported language pairs."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file containing username and password.",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter results by specific domain name (e.g. 'GEN', 'SPD').",
    )
    parser.add_argument(
        "--check-pair",
        type=str,
        nargs="*",
        default=["IT-EN", "IT-DE"],
        help="Language pairs to verify support for (default: IT-EN IT-DE).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save the full raw JSON response.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the request without connecting to the API.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("eTranslation API - /getDomains")
    print("=" * 70)
    print(f"Endpoint URL      : {DEFAULT_BASE_URL}/getDomains")
    print(f"Checking pairs    : {args.check_pair}")
    if args.domain:
        print(f"Domain filter     : {args.domain}")

    if args.dry_run:
        print("\n[DRY RUN MODE] A GET request would be sent to:")
        print(f"  GET {DEFAULT_BASE_URL}/getDomains (with HTTP Basic Auth)")
        print("\nDry run completed successfully.")
        return

    creds = get_credentials(args.config)
    if not creds:
        print("\n[!] No credentials found.", file=sys.stderr)
        print("    Please provide credentials by either:", file=sys.stderr)
        print(f"    1. Creating {CURRENT_DIR / 'config.json'} or {IMPLEMENTATION_DIR / 'config.json'}", file=sys.stderr)
        print("    2. Setting environment variables ETRANSLATION_USERNAME and ETRANSLATION_PASSWORD", file=sys.stderr)
        print("    3. Or running with --dry-run.", file=sys.stderr)
        sys.exit(1)

    username, password = creds
    print(f"\nConnecting as application: '{username}'...")

    try:
        with ETranslationClient(application=username, password=password) as client:
            domains_data = client.get_domains()
            print("[SUCCESS] /getDomains response received.")

            if args.output_json:
                args.output_json.write_text(json.dumps(domains_data, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"Full JSON response saved to {args.output_json}")

            # Normalize data structure (can be list of objects or dict of domains)
            domains_dict: dict[str, list[str]] = {}
            if isinstance(domains_data, list):
                for item in domains_data:
                    dom_name = item.get("domain", "")
                    pairs = item.get("languagePairs", [])
                    if dom_name:
                        domains_dict[dom_name] = pairs
            elif isinstance(domains_data, dict):
                for dom_name, val in domains_data.items():
                    if isinstance(val, dict):
                        domains_dict[dom_name] = val.get("languagePairs", [])
                    elif isinstance(val, list):
                        domains_dict[dom_name] = val

            print(f"\nFound {len(domains_dict)} domains: {', '.join(sorted(domains_dict.keys()))}")

            # Check requested language pairs
            if args.check_pair:
                print("\n--- Language Pair Verification ---")
                target_domains = [args.domain] if args.domain else sorted(domains_dict.keys())
                for pair in args.check_pair:
                    pair_upper = pair.upper()
                    supported_in = [d for d in target_domains if pair_upper in domains_dict.get(d, [])]
                    if supported_in:
                        print(f"  [✓] {pair_upper} is supported in domain(s): {', '.join(supported_in)}")
                    else:
                        print(f"  [✗] {pair_upper} is NOT supported in {target_domains}")

            # If filtered by domain, display pairs summary
            if args.domain:
                dom_pairs = domains_dict.get(args.domain, [])
                print(f"\nDomain '{args.domain}' supports {len(dom_pairs)} language pairs.")
                sample = dom_pairs[:10]
                print(f"Sample pairs: {sample}{' ...' if len(dom_pairs) > 10 else ''}")

    except ETranslationError as err:
        print(f"\n[ERROR] eTranslation rejected request (Code {err.error_code}): {err.error_message}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"\n[ERROR] Request failed: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
