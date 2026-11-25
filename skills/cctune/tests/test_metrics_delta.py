"""Before and after: the scan values an applied item targeted, against the values today."""
import json

import ledger
import metrics_delta


def _item(id, status, metrics):
    return {"id": id, "phase": 1, "title": f"title {id}", "risk": "safe", "status": status, "metrics": metrics,
            "ops": [{"kind": "json_set", "file": "~/.claude/settings.json", "path": [id], "value": 1}]}


def _scan(tmp_path, interactive_patterns, headless=None):
    out = {"interactive": {"sessions": 40, "patterns": interactive_patterns}, "headless": headless or {"sessions": 10},
           "subagent": {"sessions": 5}}
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(out))
    return str(path)


def test_rows_pair_each_baseline_key_with_the_value_today(tmp_home, tmp_path):
    ledger.record([_item("P2-01", "applied", {"population": "interactive", "keys": {"patterns.nudge_prompts": 72, "patterns.done_without_verify": 74}}),
                   _item("P4-01", "done", {"population": "headless", "keys": {"first_request_tokens_median": 10091}})], {}, run="2026-11-14-59a7.json")
    rows = metrics_delta.rows(_scan(tmp_path, {"nudge_prompts": 30, "done_without_verify": 74}, {"sessions": 10}))
    assert rows == [
        {"id": "P2-01", "status": "applied", "run": "2026-11-14-59a7.json", "population": "interactive",
         "key": "patterns.nudge_prompts", "before": 72, "after": 30, "change": -42},
        {"id": "P2-01", "status": "applied", "run": "2026-11-14-59a7.json", "population": "interactive",
         "key": "patterns.done_without_verify", "before": 74, "after": 74, "change": 0},
        {"id": "P4-01", "status": "done", "run": "2026-11-14-59a7.json", "population": "headless",
         "key": "first_request_tokens_median", "before": 10091, "after": None, "change": None},
    ]


def test_table_reads_as_before_after_change_and_says_when_nothing_was_recorded(tmp_home, tmp_path):
    assert metrics_delta.table([]) == "no applied or done item carries metrics yet; nothing to compare"
    ledger.record([_item("P2-01", "applied", {"population": "interactive", "keys": {"patterns.nudge_prompts": 72}})], {}, run="r.json")
    text = metrics_delta.table(metrics_delta.rows(_scan(tmp_path, {"nudge_prompts": 30})))
    header, row = text.splitlines()[:2]
    assert header.split() == ["id", "population", "key", "before", "after", "change", "since"]
    assert row.split() == ["P2-01", "interactive", "patterns.nudge_prompts", "72", "30", "-42", "r.json"]


def test_main_prints_the_table_and_writes_json_when_asked(tmp_home, tmp_path, monkeypatch, capsys):
    ledger.record([_item("P2-01", "applied", {"population": "interactive", "keys": {"patterns.nudge_prompts": 72}})], {}, run="r.json")
    out = tmp_path / "delta.json"
    monkeypatch.setattr("sys.argv", ["metrics_delta.py", "--scan", _scan(tmp_path, {"nudge_prompts": 30}), "--out", str(out)])
    metrics_delta.main()
    assert "-42" in capsys.readouterr().out and json.loads(out.read_text())[0]["change"] == -42
