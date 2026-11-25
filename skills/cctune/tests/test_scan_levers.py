"""Levers: thresholds evaluated over the finished summary, so the same data always gives the same items."""
import copy

import scan_levers

QUIET = {
    "interactive": {"sessions": 30, "first_request_tokens_median": 12000,
                    "patterns": {"nudge_prompts": 4, "done_without_verify": 3, "sessions_outside_cwd": 1,
                                 "calls_outside_cwd": 2, "sessions_in_concurrent_pairs": 0, "worktree_sessions": 0}},
    "headless": {"sessions": 20, "first_request_tokens_median": 12000,
                 "patterns": {"nudge_prompts": 0, "done_without_verify": 0}},
    "subagent": {"sessions": 500, "first_request_tokens_median": 60000,
                 "patterns": {"nudge_prompts": 0, "done_without_verify": 0}},
}


def _loud():
    out = copy.deepcopy(QUIET)
    out["headless"].update({"sessions": 2228, "first_request_tokens_median": 10091})
    out["interactive"]["patterns"].update({"nudge_prompts": 72, "done_without_verify": 72, "sessions_outside_cwd": 7,
                                           "calls_outside_cwd": 43, "sessions_in_concurrent_pairs": 10})
    return out


def _by_id(rows):
    return {row["id"]: row for row in rows}


def test_quiet_summary_triggers_nothing():
    assert scan_levers.evaluate(QUIET) == []


def test_headless_bare_fires_on_many_sessions_with_a_large_first_request():
    row = _by_id(scan_levers.evaluate(_loud()))["headless_bare"]
    assert row["population"] == "headless" and "--bare" in row["feature"]
    assert row["evidence"] == {"sessions": 2228, "first_request_tokens_median": 10091}
    assert row["docs"].startswith("https://code.claude.com/docs/en/")


def test_headless_bare_needs_both_conditions():
    out = _loud()
    out["headless"]["sessions"] = 49
    assert "headless_bare" not in _by_id(scan_levers.evaluate(out))
    out["headless"].update({"sessions": 50, "first_request_tokens_median": 4999})
    assert "headless_bare" not in _by_id(scan_levers.evaluate(out))
    out["headless"]["first_request_tokens_median"] = 5000
    assert "headless_bare" in _by_id(scan_levers.evaluate(out))


def test_stop_hook_fires_on_nudges_plus_unverified_done_claims():
    row = _by_id(scan_levers.evaluate(_loud()))["stop_hook"]
    assert row["population"] == "interactive"
    assert row["evidence"] == {"patterns.nudge_prompts": 72, "patterns.done_without_verify": 72}
    out = _loud()
    out["interactive"]["patterns"].update({"nudge_prompts": 10, "done_without_verify": 9})
    assert "stop_hook" not in _by_id(scan_levers.evaluate(out))
    out["interactive"]["patterns"]["done_without_verify"] = 10
    assert "stop_hook" in _by_id(scan_levers.evaluate(out))


def test_every_row_names_its_threshold_and_a_fetched_docs_page():
    for row in scan_levers.evaluate(_loud()):
        assert set(row) == {"id", "population", "feature", "evidence", "threshold", "docs"}
        assert row["threshold"] and row["docs"].rsplit("/", 1)[1] in scan_levers.DOCS_PAGES


def test_missing_keys_do_not_fire_or_crash():
    out = _loud()
    del out["headless"]["first_request_tokens_median"]
    del out["interactive"]["patterns"]
    assert scan_levers.evaluate(out) == []


def test_rows_are_stable_in_order():
    first = scan_levers.evaluate(_loud())
    assert [r["id"] for r in first] == ["headless_bare", "stop_hook", "additional_directories", "worktrees"]
    assert first == scan_levers.evaluate(_loud())


def test_additional_directories_fires_on_repeated_work_outside_cwd():
    row = _by_id(scan_levers.evaluate(_loud()))["additional_directories"]
    assert row["population"] == "interactive" and "additionalDirectories" in row["feature"]
    assert row["evidence"] == {"patterns.sessions_outside_cwd": 7, "patterns.calls_outside_cwd": 43}
    out = _loud()
    out["interactive"]["patterns"]["sessions_outside_cwd"] = 2
    assert "additional_directories" not in _by_id(scan_levers.evaluate(out))
    out["interactive"]["patterns"].update({"sessions_outside_cwd": 3, "calls_outside_cwd": 19})
    assert "additional_directories" not in _by_id(scan_levers.evaluate(out))


def test_worktrees_fires_on_concurrent_sessions_without_any_worktree():
    row = _by_id(scan_levers.evaluate(_loud()))["worktrees"]
    assert row["population"] == "interactive" and "claude -w" in row["feature"]
    assert row["evidence"] == {"patterns.sessions_in_concurrent_pairs": 10, "patterns.worktree_sessions": 0}
    out = _loud()
    out["interactive"]["patterns"]["worktree_sessions"] = 1
    assert "worktrees" not in _by_id(scan_levers.evaluate(out))
    out["interactive"]["patterns"].update({"worktree_sessions": 0, "sessions_in_concurrent_pairs": 3})
    assert "worktrees" not in _by_id(scan_levers.evaluate(out))


def test_scan_output_carries_levers_and_prints_them(monkeypatch, tmp_path, capsys):
    import json
    import scan
    monkeypatch.setattr(scan, "ROOT", str(tmp_path / "projects"))
    (tmp_path / "projects").mkdir()
    out = tmp_path / "scan.json"
    monkeypatch.setattr("sys.argv", ["scan.py", "--days", "1", "--out", str(out), "--no-cache"])
    scan.main()
    assert json.loads(out.read_text())["levers"] == []
    assert "== levers:" in capsys.readouterr().out
