#!/usr/bin/env python3
"""Explicit offline cleanup of old private receipt stages, never final proofs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pe_arch_vm_evidence import (
    AcceptanceReceiptError, cleanup_orphan_receipt_stages,
    MIN_STAGE_AGE_SECONDS,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review unpublished .tmp receipt stages; default preview only")
    parser.add_argument("--private-directory", required=True, type=Path)
    parser.add_argument("--min-age-hours", type=int, default=24)
    parser.add_argument("--apply", action="store_true",
                        help="Opt-in deletion. Stop all receipt writers first.")
    args = parser.parse_args(argv)
    try:
        if args.min_age_hours < 24 or args.min_age_hours > 24 * 365:
            raise AcceptanceReceiptError("Minimum age must be 24-8760 hours")
        result = cleanup_orphan_receipt_stages(
            args.private_directory,
            min_age_seconds=args.min_age_hours * 3600,
            apply=args.apply)
        print(json.dumps(result, sort_keys=True))
        return 0
    except AcceptanceReceiptError as exc:
        print(json.dumps({
            "status": "REJECTED_STAGE_CLEANUP", "reason": str(exc)},
            sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
