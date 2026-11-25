"""Sessions that ran at the same time in one project dir: the worktree signal."""
import json

import scan_concurrency
import scan_lib
from test_scan_patterns import tool_use, user_text


def _write(tmp_path, rel, start_s, end_s):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(e) for e in (user_text("go", start_s), tool_use("a", "Read", {"file_path": "/r/x"}, end_s))) + "\n")
    return str(f)


def _scan(tmp_path, layout):
    pop = scan_lib.Pop()
    for rel, (start_s, end_s) in layout.items():
        scan_lib.scan_file(_write(tmp_path, rel, start_s, end_s), lambda e, p: pop, 10 ** 9, cutoff=0)
    return pop


def test_overlapping_sessions_in_one_project_dir_count_as_a_pair(tmp_path):
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 600), "-r-app/b.jsonl": (300, 900), "-r-app/c.jsonl": (1200, 1500)})
    assert scan_concurrency.summary(pop.patterns.concurrency) == {
        "concurrent_session_pairs": 1, "sessions_in_concurrent_pairs": 2, "worktree_sessions": 0}


def test_overlap_under_a_minute_and_other_project_dirs_do_not_count(tmp_path):
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 600), "-r-app/b.jsonl": (570, 900), "-r-lib/c.jsonl": (0, 900)})
    assert scan_concurrency.summary(pop.patterns.concurrency)["concurrent_session_pairs"] == 0


def test_three_way_overlap_is_three_pairs_and_three_sessions(tmp_path):
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 1000), "-r-app/b.jsonl": (100, 1100), "-r-app/c.jsonl": (200, 1200)})
    assert scan_concurrency.summary(pop.patterns.concurrency) == {
        "concurrent_session_pairs": 3, "sessions_in_concurrent_pairs": 3, "worktree_sessions": 0}


def test_worktree_sessions_are_counted_and_kept_out_of_pairs(tmp_path):
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 1000), "-r-app--claude-worktrees-x/b.jsonl": (100, 1100),
                           "-r-app--claude-worktrees-y/c.jsonl": (100, 1100)})
    assert scan_concurrency.summary(pop.patterns.concurrency) == {
        "concurrent_session_pairs": 0, "sessions_in_concurrent_pairs": 0, "worktree_sessions": 2}


def test_spans_hold_hashes_and_seconds_only(tmp_path):
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 600)})
    (span,) = pop.patterns.concurrency.spans.values()
    group, worktree, first, last = span
    assert len(group) == 12 and "app" not in group and worktree == 0 and last - first == 600


def test_session_without_timestamps_has_no_span(tmp_path):
    f = tmp_path / "-r-app" / "a.jsonl"
    f.parent.mkdir()
    f.write_text(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
    pop = scan_lib.Pop()
    scan_lib.scan_file(str(f), lambda e, p: pop, 10 ** 9, cutoff=0)
    assert pop.patterns.concurrency.spans == {}


def test_patterns_summary_carries_the_keys(tmp_path):
    import scan_patterns
    pop = _scan(tmp_path, {"-r-app/a.jsonl": (0, 600), "-r-app/b.jsonl": (300, 900)})
    summary = scan_patterns.summary(pop.patterns, 2)
    assert summary["concurrent_session_pairs"] == 1 and summary["worktree_sessions"] == 0
