"""The ledger is the one place state lives: append-only events keyed by fingerprint."""
import json
import os
import stat

import ledger
import plan_fingerprint as fp


def _item(id="P1-01", path=("autoCompactWindow",), status="proposed", **over):
    base = {"id": id, "phase": 1, "title": f"title {id}", "risk": "safe", "status": status,
            "ops": [{"kind": "json_set", "file": "~/.claude/settings.json", "path": list(path), "value": 1}]}
    base.update(over)
    return base


def test_record_appends_one_line_per_changed_item_and_reloads_it(tmp_home):
    path = ledger.ledger_path()
    before = {fp.fingerprint(_item()): {"status": "proposed"}}
    items = [_item(status="applied", applied_at="2026-11-14T10:00:00", files=["/x"], backup="/b"), _item("P1-02", ("b",))]
    ledger.record(items, before, run="2026-11-13-59a7.json")
    lines = path.read_text().splitlines()
    assert len(lines) == 1 and stat.S_IMODE(os.stat(path).st_mode) == 0o600
    ev = json.loads(lines[0])
    assert ev["id"] == "P1-01" and ev["status"] == "applied" and ev["run"] == "2026-11-13-59a7.json" and ev["backup"] == "/b"
    state = ledger.load_state()
    assert state[fp.fingerprint(_item())]["status"] == "applied" and state[fp.fingerprint(_item())]["files"] == ["/x"]


def test_last_event_wins_and_bad_lines_are_skipped_with_a_warning(tmp_home):
    path = ledger.ledger_path()
    key = fp.fingerprint(_item())
    path.write_text(json.dumps({"fp": key, "id": "P1-01", "status": "applied", "t": "1"}) + "\n"
                    + "not json\n"
                    + json.dumps({"fp": key, "id": "P1-01", "status": "rolled_back", "t": "2"}) + "\n")
    state = ledger.load_state()
    assert state[key]["status"] == "rolled_back"
    assert ledger.warnings() == ["ledger line 2 unreadable, skipped"]


def test_overlay_sets_state_from_ledger_and_leaves_unknown_items_alone(tmp_home):
    known, unknown = _item(), _item("P1-02", ("b",), status="done")
    ledger.record([_item(status="applied", backup="/b", files=["/x"])], {}, run="r1")
    plan = {"items": [known, unknown]}
    ledger.overlay(plan)
    assert known["status"] == "applied" and known["backup"] == "/b" and unknown["status"] == "done"


def test_overlay_restores_proposed_when_ledger_says_so(tmp_home):
    stale = _item(status="applied", backup="/old")
    ledger.record([_item(status="proposed")], {fp.fingerprint(_item()): {"status": "applied"}}, run="r1")
    ledger.overlay({"items": [stale]})
    assert stale["status"] == "proposed" and "backup" not in stale


def test_page_url_round_trips(tmp_home):
    assert ledger.page_url() is None
    ledger.set_page_url("https://claude.ai/artifact/abc")
    assert ledger.page_url() == "https://claude.ai/artifact/abc"
    ledger.overlay(plan := {"items": []})
    assert plan["page_url"] == "https://claude.ai/artifact/abc"


def test_snapshot_keeps_only_state_fields():
    it = _item(status="failed", error="boom", applied_at="t", done_at="d", files=["/x"], backup="/b", why="w")
    assert ledger.snapshot(it) == {"status": "failed", "error": "boom", "applied_at": "t", "done_at": "d", "files": ["/x"], "backup": "/b"}


def test_bootstrap_imports_legacy_statuses_from_every_plan_oldest_first(tmp_home):
    plans = tmp_home / ".claude" / "tune" / "plans"
    old = {"generated": "2026-11-10T00:00:00", "items": [_item(status="applied", backup="/b1"), _item("P1-02", ("b",), status="done")]}
    new = {"generated": "2026-11-13T00:00:00", "items": [_item(status="proposed"), _item("P9-09", ("c",))], "page_url": "https://claude.ai/artifact/p"}
    (plans / "a.json").write_text(json.dumps(old))
    (plans / "b.json").write_text(json.dumps(new))
    (plans / "latest.json").symlink_to(plans / "a.json")
    imported = ledger.bootstrap()
    state = ledger.load_state()
    assert imported == 2 and state[fp.fingerprint(_item())]["status"] == "applied"
    assert state[fp.fingerprint(_item("P1-02", ("b",)))]["status"] == "done"
    assert ledger.page_url() == "https://claude.ai/artifact/p"
    assert not (plans / "latest.json").exists() and ledger.bootstrap() == 0


def test_history_rows_name_id_run_status_and_title(tmp_home):
    ledger.record([_item(status="applied", backup="/b")], {}, run="r1")
    rows = ledger.history()
    assert rows == [{"fp": fp.fingerprint(_item()), "id": "P1-01", "run": "r1", "status": "applied", "title": "title P1-01"}]


def test_functions_are_short():
    import inspect
    for name, fn in inspect.getmembers(ledger, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name
