"""Golden-set CLI.

python -m azinco_worker.goldens check   <set_dir>                 # integrity (CI)
python -m azinco_worker.goldens build   <set_dir> [--seed N] [--count N]   # [MOCK] synthetic
python -m azinco_worker.goldens run     <set_dir> --out report.json        # [MOCK] provider
python -m azinco_worker.goldens compare <report.json> <baseline.json>      # regression gate
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from azinco_worker.gateway import Budget
from azinco_worker.goldens.core import (
    GoldenSetError,
    Report,
    compare,
    load_set,
    run,
    score,
    write_set,
)
from azinco_worker.goldens.predictors import gateway_categorizer
from azinco_worker.goldens.synth import SYNTHETIC_CHART, generate
from azinco_worker.graph.demo import mock_gateway


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="azinco_worker.goldens")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("set_dir", type=Path)
    b = sub.add_parser("build")
    b.add_argument("set_dir", type=Path)
    b.add_argument("--seed", type=int, default=20261118)
    b.add_argument("--count", type=int, default=100)
    r = sub.add_parser("run")
    r.add_argument("set_dir", type=Path)
    r.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("compare")
    m.add_argument("report", type=Path)
    m.add_argument("baseline", type=Path)
    args = p.parse_args(argv)

    try:
        if args.cmd == "check":
            g = load_set(args.set_dir)
            m_ = g.manifest
            print(
                f"GOLDEN-SET-OK {m_.set_id}/{m_.version} status={m_.status.value} "
                f"items={len(g.items)} policy={m_.data_policy}"
            )
        elif args.cmd == "build":
            items = generate(seed=args.seed, count=args.count)
            g = write_set(
                args.set_dir,
                {
                    "set_id": args.set_dir.parent.name,
                    "version": args.set_dir.name,
                    "status": "draft",
                    "data_policy": "synthetic",
                    "description": "[MOCK] Synthetic invoices, bills and receipts for invented "
                    "PK and GB businesses; labels proposed by the generator.",
                    "generator": f"azinco_worker.goldens.synth seed={args.seed} count={args.count}",
                    "created": datetime.now(UTC).date().isoformat(),
                    "labelled_by": "generator ([MOCK]) - awaiting Reviewer of Record confirmation",
                    "chart_of_accounts": SYNTHETIC_CHART,
                },
                items,
            )
            print(f"BUILT {len(g.items)} items -> {args.set_dir}")
        elif args.cmd == "run":
            g = load_set(args.set_dir)
            # A golden run is many tasks at once: size the budget to the set (2 attempts per item).
            gateway, _ = mock_gateway(Budget(max_calls=2 * len(g.items), max_tokens=10_000_000))
            predictor, info = gateway_categorizer(gateway)
            report = score(
                g, run(g, predictor), info, datetime.now(UTC).isoformat(timespec="seconds")
            )
            args.out.write_text(report.to_json() + "\n", encoding="utf-8")
            print(f"REPORT {args.out}: {report.metrics}")
        else:
            problems = compare(
                Report.from_json(args.report.read_text(encoding="utf-8")),
                Report.from_json(args.baseline.read_text(encoding="utf-8")),
            )
            for line in problems:
                print(f"REGRESSION {line}", file=sys.stderr)
            if problems:
                return 1
            print("NO-REGRESSION")
    except GoldenSetError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
