"""Print daily totals from logs/runs.jsonl.

python scripts/usage_report.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "logs" / "runs.jsonl"


def main() -> int:
    if not LOG.exists():
        print("No runs logged yet.")
        return 0
    days: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = days[rec.get("timestamp", "")[:10]]
        d["runs"] += 1
        d["rows"] += rec.get("input_rows", 0)
        d["cost"] += rec.get("estimated_cost_usd", 0) or 0
        d["calls"] += rec.get("model_calls", 0) or 0
        d[rec.get("outcome", "unknown")] += 1

    print(f"{'day':<12}{'runs':>6}{'rows':>8}{'calls':>8}{'cost $':>10}{'failed':>8}{'capped':>8}{'fail %':>8}")
    for day in sorted(days):
        d = days[day]
        fail_rate = d["failed"] / d["runs"] * 100 if d["runs"] else 0
        print(
            f"{day:<12}{int(d['runs']):>6}{int(d['rows']):>8}{int(d['calls']):>8}{d['cost']:>10.4f}"
            f"{int(d['failed']):>8}{int(d['cap_hit']):>8}{fail_rate:>7.0f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
