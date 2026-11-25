"""Levers: thresholds evaluated over the finished `scan.json`, the same way every run.

A brief reads numbers and may word them differently each audit. A lever is a fixed rule over
named keys: when the data crosses the threshold the row appears with the values that crossed
it, otherwise it does not. The brief only words the plan item. Each row names the Claude Code
feature that removes the pattern and the docs page (one `docs_fetch.sh` fetches) that
documents it. Thresholds are heuristics; the row says which.
"""
DOCS_BASE = "https://code.claude.com/docs/en/"
DOCS_PAGES = ("cli-reference", "headless", "hooks", "hooks-guide", "worktrees", "settings")
ROW_FIELDS = ("id", "population", "feature", "evidence", "threshold", "docs")

HEADLESS_MIN_SESSIONS = 50
HEADLESS_MIN_FIRST_REQUEST = 5000
STOP_HOOK_MIN_EVENTS = 20


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
