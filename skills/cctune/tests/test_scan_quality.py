"""Quality detectors: loops, failed edits, test-file edits in fix sessions. Counts only."""
import json

import scan_lib
import scan_patterns
from test_scan_patterns import assistant_text, bash, scan, tool_result, tool_use, user_text


def _scan_into(pop, tmp_path, events, name):
    f = tmp_path / name
    f.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    scan_lib.scan_file(str(f), lambda e, p: pop, 10 ** 9, cutoff=0)


def _summary(pop):
    return scan_patterns.summary(pop.patterns, len(pop.sessions))


def test_repeated_tool_calls_count_identical_consecutive_input_per_tool(tmp_path):
    pop = scan(tmp_path, [bash("a", "pytest -q"), bash("b", "pytest -q"), bash("c", "ls"), bash("d", "pytest -q"),
                          tool_use("e", "Grep", {"pattern": "x", "path": "/r"}), tool_use("f", "Grep", {"path": "/r", "pattern": "x"}),
                          tool_use("g", "Read", {"file_path": "/r/a"}), tool_use("h", "Read", {"file_path": "/r/b"})])
    assert _summary(pop)["repeated_tool_calls"] == [("Bash", 1), ("Grep", 1)]


def test_search_loop_is_three_consecutive_grep_or_glob_calls(tmp_path):
    searches = [tool_use(f"s{i}", "Grep" if i % 2 else "Glob", {"pattern": f"p{i}"}) for i in range(4)]
    pop = scan(tmp_path, searches + [tool_use("r", "Read", {"file_path": "/r/a"})] +
               [tool_use(f"t{i}", "Grep", {"pattern": f"q{i}"}) for i in range(2)] +
               [tool_use(f"u{i}", "Read", {"file_path": f"/r/{i}"}) for i in range(3)])
    assert _summary(pop)["search_loops_3plus"] == 1


def test_failed_edit_streaks_and_error_rate_by_tool(tmp_path):
    edit = {"file_path": "/r/x.py", "old_string": "a", "new_string": "b"}
    pop = scan(tmp_path, [tool_use("a", "Edit", edit), tool_result("a", "no match", 1, is_error=True),
                          tool_use("b", "Edit", edit, 2), tool_result("b", "no match", 3, is_error=True),
                          tool_use("c", "Edit", edit, 4), tool_result("c", "no match", 5, is_error=True),
                          tool_use("d", "Edit", edit, 6), tool_result("d", "ok", 7),
                          tool_use("e", "Write", {"file_path": "/r/y", "content": "z"}, 8), tool_result("e", "err", 9, is_error=True),
                          bash("f", "ls", 10), tool_result("f", "err", 11, is_error=True)])
    s = _summary(pop)
    assert s["failed_edit_streaks"] == 1
    assert s["tool_error_rate"] == {"Edit": [3, 4, 0.75], "Bash": [1, 1, 1.0], "Write": [1, 1, 1.0]}


def test_fix_sessions_with_test_file_edit_then_passing_test_command(tmp_path):
    fix = [user_text("fix the failing login bug", 0), tool_use("e", "Edit", {"file_path": "/r/tests/test_login.py"}, 1)]
    pop = scan(tmp_path, fix + [bash("t", "pytest -q", 2), tool_result("t", "1 passed", 3)], "a.jsonl")
    _scan_into(pop, tmp_path, fix + [bash("t", "pytest -q", 2), tool_result("t", "1 failed", 3, is_error=True)], "b.jsonl")
    _scan_into(pop, tmp_path, [user_text("fix the crash", 0), tool_use("e", "Edit", {"file_path": "/r/src/login.py"}, 1),
                               bash("t", "pytest -q", 2), tool_result("t", "ok", 3)], "c.jsonl")
    _scan_into(pop, tmp_path, [user_text("add a dark theme", 0), tool_use("e", "Edit", {"file_path": "/r/tests/test_theme.py"}, 1),
                               bash("t", "pytest -q", 2), tool_result("t", "ok", 3)], "d.jsonl")
    s = _summary(pop)
    assert s["fix_sessions"] == 3 and s["test_file_edits_in_fix_sessions"] == 1


def test_test_path_shapes():
    import scan_quality
    yes = ["/r/tests/test_x.py", "/r/test_x.py", "/r/src/x_test.go", "/r/src/x.test.ts", "/r/src/x.spec.tsx", "/r/__tests__/a.js", "/r/spec/a_spec.rb"]
    no = ["/r/src/x.py", "/r/testing/notes.md", "/r/contest/x.py", "/r/src/latest.ts"]
    assert all(scan_quality.is_test_path(p) for p in yes)
    assert not any(scan_quality.is_test_path(p) for p in no)


def test_summary_keeps_done_claim_wiring_after_test_re_move(tmp_path):
    pop = scan(tmp_path, [user_text("fix", 0), bash("b", "pytest -q", 1), tool_result("b", "ok", 2),
                          assistant_text("Tests pass.", 3)])
    assert pop.patterns.done_claims == 1 and pop.patterns.done_without_verify == 0


def test_quality_functions_are_short():
    import inspect
    import scan_quality
    for name, fn in inspect.getmembers(scan_quality, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name
