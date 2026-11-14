#!/usr/bin/env python3
"""Share of the lines an agent added that the next commit on the file still carries.

Streams one transcript, collects the lines each Edit/Write added to files under the repo,
then reads the first commit that touched each file after the edit (within `--days`) and
counts which added lines are present there. Prints counts only; no line content.
Usage: edit_survival.py --session <transcript.jsonl> --repo <path> [--days 7]
"""
import argparse
import collections
import datetime as dt
import json
import os
import subprocess
import sys

MIN_LINE_CHARS = 8
GIT_TIMEOUT_S = 60
EDIT_TOOLS = ("Edit", "Write", "MultiEdit")


def _lines(text):
    return {ln.strip() for ln in str(text or "").splitlines() if len(ln.strip()) >= MIN_LINE_CHARS}


def added_lines(tool, inp):
    """New lines of one edit: `new_string` minus `old_string`, or the whole `content` of a Write."""
    if tool == "Write":
        return _lines(inp.get("content"))
    return _lines(inp.get("new_string")) - _lines(inp.get("old_string"))


def collect_edits(session_path, repo):
    """`{relpath: (first edit timestamp, set of added lines)}` for files under `repo`."""
    root = os.path.realpath(repo) + os.sep
    edits = {}
    with open(session_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            for tool, inp, when in _tool_uses(raw):
                path = os.path.realpath(str(inp.get("file_path", "")))
                if tool not in EDIT_TOOLS or not path.startswith(root):
                    continue
                first, lines = edits.get(path[len(root):], (when, set()))
                edits[path[len(root):]] = (min(first, when), lines | added_lines(tool, inp))
    return edits


def _tool_uses(raw):
    try:
        ev = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(ev, dict) or ev.get("type") != "assistant":
        return []
    when = str(ev.get("timestamp", ""))
    content = (ev.get("message") or {}).get("content")
    blocks = content if isinstance(content, list) else []
    return [(b.get("name"), b.get("input") or {}, when) for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]


def next_commit_lines(repo, relpath, since_iso, days):
    """Lines of `relpath` at the first commit touching it in (since, since + days]; None when there is none."""
    start = dt.datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    until = (start + dt.timedelta(days=days)).isoformat()
    log = subprocess.run(["git", "-C", repo, "log", f"--since={start.isoformat()}", f"--until={until}", "--reverse",
                          "--format=%H", "--", relpath], capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    commit = log.stdout.split("\n", 1)[0].strip()
    if not commit:
        return None
    show = subprocess.run(["git", "-C", repo, "show", f"{commit}:{relpath}"], capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    return _lines(show.stdout) if show.returncode == 0 else set()


def survival(session_path, repo, days):
    totals = collections.Counter()
    for relpath, (when, added) in collect_edits(session_path, repo).items():
        totals["files"] += 1
        totals["lines_added"] += len(added)
        committed = next_commit_lines(repo, relpath, when, days) if when else None
        if committed is None:
            totals["files_without_commit"] += 1
            continue
        totals["lines_surviving"] += len(added & committed)
    share = round(totals["lines_surviving"] / totals["lines_added"], 3) if totals["lines_added"] else None
    return {"files": totals["files"], "files_without_commit": totals["files_without_commit"],
            "lines_added": totals["lines_added"], "lines_surviving": totals["lines_surviving"], "survival": share}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    print(json.dumps(survival(a.session, os.path.expanduser(a.repo), a.days)))


if __name__ == "__main__":
    sys.exit(main())
