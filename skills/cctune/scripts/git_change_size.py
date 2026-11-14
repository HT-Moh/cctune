#!/usr/bin/env python3
"""Lines changed per commit, against the review-size bands brief G reads.

Read-only `git log --numstat` over each repo since a date. Binary rows and lockfiles are
skipped. Bands: a median under 85 lines is the elite band, a median over 209 is where PR
review stops working (LinearB 2025); the flag names the second case.
Usage: git_change_size.py --repos a,b --since YYYY-MM-DD
"""
import argparse
import json
import os
import subprocess
import sys

ELITE_LINES = 85
NEEDS_FOCUS_LINES = 209
LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", "poetry.lock", "Cargo.lock", "go.sum", "composer.lock")
GIT_TIMEOUT_S = 120


def parse_numstat(text):
    """Added plus deleted lines over the rows of one commit; `-` (binary) and lockfiles skipped."""
    total = 0
    for row in text.splitlines():
        parts = row.split("\t")
        if len(parts) != 3 or parts[0] == "-" or os.path.basename(parts[2]) in LOCKFILES:
            continue
        total += int(parts[0]) + int(parts[1])
    return total


def commit_sizes(repo, since):
    """One line count per commit; commits are separated by their `%H` header line."""
    out = subprocess.run(["git", "-C", repo, "log", f"--since={since}", "--numstat", "--format=@@%H", "--no-merges"],
                         capture_output=True, text=True, check=True, timeout=GIT_TIMEOUT_S).stdout
    sizes = []
    for chunk in out.split("@@")[1:]:
        body = chunk.split("\n", 1)[1] if "\n" in chunk else ""
        sizes.append(parse_numstat(body))
    return sizes


def _pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def repo_stats(repo, since):
    sizes = commit_sizes(repo, since)
    if not sizes:
        return {"commits": 0}
    n = len(sizes)
    return {"commits": n, "lines_p50": _pct(sizes, 0.5), "lines_p90": _pct(sizes, 0.9),
            "share_under_85": round(sum(s < ELITE_LINES for s in sizes) / n, 2),
            "share_over_209": round(sum(s > NEEDS_FOCUS_LINES for s in sizes) / n, 2)}


def flag_for(stats):
    if stats.get("lines_p50", 0) > NEEDS_FOCUS_LINES:
        return f"p50 above {NEEDS_FOCUS_LINES}: split the work"
    if stats.get("lines_p50", 0) < ELITE_LINES and stats.get("commits"):
        return f"p50 under {ELITE_LINES}: elite band"
    return ""


def repo_row(repo, since):
    name = os.path.basename(os.path.normpath(repo))
    if not os.path.isdir(os.path.join(repo, ".git")):
        return {"repo": name, "error": "not a git repo"}
    try:
        stats = repo_stats(repo, since)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"repo": name, "error": type(exc).__name__}
    return {"repo": name, **stats, "flag": flag_for(stats)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repos", required=True, help="comma-separated repo paths")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    a = ap.parse_args(argv)
    for repo in filter(None, a.repos.split(",")):
        print(json.dumps(repo_row(os.path.expanduser(repo), a.since)))


if __name__ == "__main__":
    sys.exit(main())
