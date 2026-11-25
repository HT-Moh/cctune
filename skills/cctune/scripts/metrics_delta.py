#!/usr/bin/env python3
"""Before and after: the scan values an applied item targeted, against the values in today's scan.

An item may carry `metrics`: the population and the `scan.json` keys whose values justified
it. `cctune-apply` keeps those values in the ledger event that records the item as applied or
done. This script pairs each kept value with the same key in a newer `scan.json`, so the next
report can say whether the change moved the number. Counts and keys only; no transcript is read.
Usage: metrics_delta.py --scan scan.json [--out delta.json]
"""
import argparse
import json
import os
import sys

APPLY_SCRIPTS = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "cctune-apply", "scripts")
sys.path.insert(0, os.path.realpath(APPLY_SCRIPTS))
import ledger  # noqa: E402

COLUMNS = ("id", "population", "key", "before", "after", "change", "since")
EMPTY = "no applied or done item carries metrics yet; nothing to compare"


def lookup(summary, dotted):
    value = summary
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def rows(scan_path):
    """One row per (settled item, metric key), in ledger order."""
    with open(scan_path, encoding="utf-8") as fh:
        scan = json.load(fh)
    out = []
    for base in ledger.baselines():
        population = base["metrics"].get("population", "")
        summary = scan.get(population) or {}
        for key, before in base["metrics"].get("keys", {}).items():
            after = lookup(summary, key)
            change = None if after is None else round(after - before, 3)
            out.append({"id": base["id"], "status": base["status"], "run": base["run"], "population": population,
                        "key": key, "before": before, "after": after, "change": change})
    return out


def _cell(row, column):
    if column == "since":
        return str(row["run"])
    value = row[column]
    return "n/a" if value is None else str(value)


def table(delta_rows):
    if not delta_rows:
        return EMPTY
    cells = [COLUMNS] + [tuple(_cell(r, c) for c in COLUMNS) for r in delta_rows]
    widths = [max(len(line[i]) for line in cells) for i in range(len(COLUMNS))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip() for line in cells)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    delta_rows = rows(a.scan)
    if a.out:
        with open(os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as fh:
            json.dump(delta_rows, fh, indent=1)
    print(table(delta_rows))


if __name__ == "__main__":
    main()
