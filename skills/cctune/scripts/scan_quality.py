"""Quality detectors for one population: loops, failed edits, test-file edits in fix sessions.

Each one has a measured counterpart: step repetition is the most frequent agent failure
mode, recovery odds fall with every failed edit, and a fix that edits the test file is the
usual way an agent passes an impossible task. Counts only; no path or content is kept.
"""
import collections
import hashlib
import json
import re

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SEARCH_TOOLS = ("Grep", "Glob")
SEARCH_LOOP = 3
EDIT_FAIL_STREAK = 2
ERROR_RATE_ROWS = 10
TEST_RE = re.compile(r"\b(pytest|jest|vitest|mocha|cargo test|go test|make (test|check)|(npm|pnpm|yarn|bun) (run )?test|"
                     r"tox|unittest|rspec|phpunit|ruff|mypy|tsc|eslint|golangci-lint)\b")
FIX_PROMPT_RE = re.compile(r"\b(fix|bug|error|fails?|failing|failed|broken|crash(es|ing)?|regression|not working)\b", re.I)
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|_(test|spec)\.\w+$|\.(test|spec)\.[cm]?[jt]sx?$")


def is_test_path(path):
    return bool(TEST_PATH_RE.search(str(path)))


def input_digest(inp):
    return hashlib.sha256(json.dumps(inp, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class Quality:
    """Population counters."""

    def __init__(self):
        self.repeated_calls = collections.Counter()
        self.search_loops = 0
        self.failed_edit_streaks = 0
        self.tool_calls = collections.Counter()
        self.tool_errors = collections.Counter()
        self.fix_sessions = 0
        self.fix_sessions_test_edits = 0


class SessionQuality:
    """Per-session memory: the last call, the current runs, and the fix-task flags."""

    def __init__(self):
        self.last_call = None
        self.search_run = 0
        self.edit_fail_run = 0
        self.fix_task = None
        self.test_edited = False
        self.test_passed_after = False


def on_prompt(text, sq):
    """The first prompt decides whether the session is a fix task."""
    if sq.fix_task is None:
        sq.fix_task = bool(FIX_PROMPT_RE.search(text))


def on_tool_use(name, inp, sq, q):
    q.tool_calls[name] += 1
    call = (name, input_digest(inp))
    if call == sq.last_call:
        q.repeated_calls[name] += 1
    sq.last_call = call
    _note_search(name, sq, q)
    if name in EDIT_TOOLS and sq.fix_task and is_test_path(inp.get("file_path") or inp.get("notebook_path") or ""):
        sq.test_edited = True


def _note_search(name, sq, q):
    if name not in SEARCH_TOOLS:
        sq.search_run = 0
        return
    sq.search_run += 1
    if sq.search_run == SEARCH_LOOP:
        q.search_loops += 1


def on_tool_result(name, inp, is_error, sq, q):
    if is_error:
        q.tool_errors[name] += 1
    if name in EDIT_TOOLS:
        sq.edit_fail_run = sq.edit_fail_run + 1 if is_error else 0
        if sq.edit_fail_run == EDIT_FAIL_STREAK:
            q.failed_edit_streaks += 1
    if name == "Bash" and sq.test_edited and not is_error and TEST_RE.search(str(inp.get("command", ""))):
        sq.test_passed_after = True


def finish_session(sq, q):
    if sq.fix_task:
        q.fix_sessions += 1
        q.fix_sessions_test_edits += int(sq.test_edited and sq.test_passed_after)


def summary(q):
    rate = {name: [n, q.tool_calls[name], round(n / q.tool_calls[name], 3) if q.tool_calls[name] else None]
            for name, n in q.tool_errors.most_common(ERROR_RATE_ROWS)}
    return {"repeated_tool_calls": q.repeated_calls.most_common(10), "search_loops_3plus": q.search_loops,
            "failed_edit_streaks": q.failed_edit_streaks, "tool_error_rate": rate,
            "fix_sessions": q.fix_sessions, "test_file_edits_in_fix_sessions": q.fix_sessions_test_edits}
