#!/usr/bin/env python3
"""Reject server errors even when the CLI process reports success."""
import json
import sys


def check(lines):
    responses = 0
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue  # CLI file/progress messages are not query results.
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            print("Invalid JSON query response", file=sys.stderr)
            return 1
        status = result.get("status_class", "")
        if not status:
            continue
        responses += 1
        if result.get("error") or result.get("error_code") or status[:2] not in ("00", "01", "02"):
            print(f"Geode query failed: {status}", file=sys.stderr)
            return 1
    if not responses:
        print("Geode query returned no status-bearing response", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as output:
        sys.exit(check(output))
