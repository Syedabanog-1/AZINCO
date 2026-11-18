"""`python -m azinco_rules check <dir>`: load all packs, run their tests, enforce the gate.

CI runs this on `rule-packs/` so a pack with failing tests or missing citations cannot be merged
in a gated status (BS §8.2). Exit code 0 = all packs valid.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from azinco_rules.engine import Registry, RuleEngineError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="azinco-rules")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="validate all packs under a directory")
    check.add_argument("root", type=Path)
    args = parser.parse_args(argv)

    root: Path = args.root
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        registry = Registry.load_dir(root)
    except RuleEngineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    rows = list(registry.summary())
    for jurisdiction, layer, version, status, rules in rows:
        print(f"OK  {jurisdiction}/{layer}/{version}  status={status}  rules={rules}")
    print(f"RULE-PACKS-OK ({len(rows)} pack(s); empty until sourced content is approved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
