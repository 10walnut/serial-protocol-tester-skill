#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from protocol_core import validate_protocol_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a serial_protocol.v1 JSON file.")
    parser.add_argument("protocol", type=Path, help="Path to the protocol JSON file")
    args = parser.parse_args()

    try:
        data = json.loads(args.protocol.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"ERROR: cannot read {args.protocol}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return 2

    errors = validate_protocol_data(data)
    if errors:
        print(f"INVALID: {args.protocol}", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    command_count = len(data["commands"])
    print(f"OK: {args.protocol} ({command_count} commands, schema serial_protocol.v1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
