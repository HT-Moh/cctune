"""Levers: thresholds evaluated over the finished `scan.json`, the same way every run.

A brief reads numbers and may word them differently each audit. A lever is a fixed rule over
named keys: when the data crosses the threshold the row appears with the values that crossed
it, otherwise it does not. The brief only words the plan item. Each row names the Claude Code
feature that removes the pattern and the docs page (one `docs_fetch.sh` fetches) that
documents it. Thresholds are heuristics; the row says which.
"""
DOCS_BASE = "https://code.claude.com/docs/en/"
DOCS_PAGES = ("cli-reference", "headless", "hooks", "hooks-guide", "worktrees", "settings", "permissions")
ROW_FIELDS = ("id", "population", "feature", "evidence", "threshold", "docs")

HEADLESS_MIN_SESSIONS = 50
HEADLESS_MIN_FIRST_REQUEST = 5000
STOP_HOOK_MIN_EVENTS = 20
OUTSIDE_MIN_SESSIONS = 3
OUTSIDE_MIN_CALLS = 20
CONCURRENT_MIN_SESSIONS = 4


def _lookup(summary, dotted):
    value = summary
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _headless_bare(values):
    return values["sessions"] >= HEADLESS_MIN_SESSIONS and values["first_request_tokens_median"] >= HEADLESS_MIN_FIRST_REQUEST


def _stop_hook(values):
    return values["patterns.nudge_prompts"] + values["patterns.done_without_verify"] >= STOP_HOOK_MIN_EVENTS


def _additional_directories(values):
    return values["patterns.sessions_outside_cwd"] >= OUTSIDE_MIN_SESSIONS and values["patterns.calls_outside_cwd"] >= OUTSIDE_MIN_CALLS


def _worktrees(values):
    return values["patterns.sessions_in_concurrent_pairs"] >= CONCURRENT_MIN_SESSIONS and values["patterns.worktree_sessions"] == 0


LEVERS = (
    {"id": "headless_bare", "population": "headless",
     "keys": ("sessions", "first_request_tokens_median"), "rule": _headless_bare,
     "feature": "claude -p --bare with --settings, --mcp-config or --append-system-prompt-file for what the run needs",
     "threshold": f"sessions >= {HEADLESS_MIN_SESSIONS} and first_request_tokens_median >= {HEADLESS_MIN_FIRST_REQUEST} (heuristic)",
     "docs": "cli-reference"},
    {"id": "stop_hook", "population": "interactive",
     "keys": ("patterns.nudge_prompts", "patterns.done_without_verify"), "rule": _stop_hook,
     "feature": "Stop hook that runs the project's done-check and blocks the stop while it fails",
     "threshold": f"nudge_prompts + done_without_verify >= {STOP_HOOK_MIN_EVENTS} (heuristic)",
     "docs": "hooks"},
    {"id": "additional_directories", "population": "interactive",
     "keys": ("patterns.sessions_outside_cwd", "patterns.calls_outside_cwd"), "rule": _additional_directories,
     "feature": "permissions.additionalDirectories in settings for the second repository, or --add-dir per session",
     "threshold": f"sessions_outside_cwd >= {OUTSIDE_MIN_SESSIONS} and calls_outside_cwd >= {OUTSIDE_MIN_CALLS} (heuristic)",
     "docs": "permissions"},
    {"id": "worktrees", "population": "interactive",
     "keys": ("patterns.sessions_in_concurrent_pairs", "patterns.worktree_sessions"), "rule": _worktrees,
     "feature": "claude -w <name> for each parallel session on one checkout",
     "threshold": f"sessions_in_concurrent_pairs >= {CONCURRENT_MIN_SESSIONS} and worktree_sessions == 0 (heuristic)",
     "docs": "worktrees"},
)


def evaluate(out):
    """Rows for every lever whose rule holds; stable order, values copied into `evidence`."""
    rows = []
    for lever in LEVERS:
        summary = out.get(lever["population"]) or {}
        values = {key: _lookup(summary, key) for key in lever["keys"]}
        if any(v is None for v in values.values()) or not lever["rule"](values):
            continue
        rows.append({"id": lever["id"], "population": lever["population"], "feature": lever["feature"],
                     "evidence": values, "threshold": lever["threshold"], "docs": DOCS_BASE + lever["docs"]})
    return rows
