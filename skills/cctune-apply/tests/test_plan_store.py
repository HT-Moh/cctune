import fcntl
import json
import os
import stat

import pytest

import plan_store
from plan_schema import PlanError

SETTINGS = "~/.claude/settings.json"


def v2_item(id="P1-01", status="proposed", **over):
    return {**{"id": id, "phase": 1, "title": "t", "risk": "safe", "why": "w", "evidence": "e",
            "docs": "https://x", "impact": "i", "depends_on": [], "consumers": [], "reversible": "full",
            "blast_radius": "user", "takes_effect": "next-session", "contains_secret": False, "checks": [],
            "status": status,
            "ops": [{"kind": "json_set", "file": SETTINGS, "path": ["autoCompactWindow"], "value": 400000}]}, **over}


def v2_plan(*items):
    return {"schema": 2, "generated": "g", "window_days": 30, "claude_version": "v", "summary": "s",
            "items": list(items) or [v2_item()]}


def test_load_refuses_plan_outside_plans_dir(tmp_home):
    outside = tmp_home / "plan.json"
    outside.write_text(json.dumps(v2_plan()))
    with pytest.raises(PlanError, match="plans"):
        plan_store.load_plan(str(outside))


def test_load_migrates_v1_and_validates(plan_file):
    v1 = v2_plan()
    v1["schema"] = 1
    for k in ("consumers", "reversible", "blast_radius", "takes_effect", "contains_secret", "checks"):
        v1["items"][0].pop(k)
    v1["items"][0]["verify"] = "look"
    path = plan_file(v1)
    plan, loaded_path = plan_store.load_plan(str(path))
    assert plan["schema"] == 2 and plan["items"][0]["checks"][0]["kind"] == "note"
    assert loaded_path == path


def test_load_reports_invalid_plan(plan_file):
    bad = v2_plan()
    bad["items"][0]["risk"] = "yolo"
    path = plan_file(bad)
    with pytest.raises(PlanError, match="risk"):
        plan_store.load_plan(str(path))


def test_load_default_uses_the_newest_plan_by_generated_not_by_name(plan_file):
    older = v2_plan()
    older["generated"] = "2026-11-10T00:00:00"
    newer = v2_plan()
    newer["generated"] = "2026-11-13T00:00:00"
    plan_file(older, "z-later-name.json")
    expected = plan_file(newer, "a-earlier-name.json")
    plan, loaded = plan_store.load_plan(None)
    assert loaded == expected and plan["generated"] == "2026-11-13T00:00:00"


def test_load_without_any_plan_says_run_cctune(tmp_home):
    with pytest.raises(PlanError, match="Run /cctune first"):
        plan_store.load_plan(None)


def test_load_overlays_ledger_state_onto_the_plan(plan_file):
    import ledger
    path = plan_file(v2_plan())
    ledger.record([v2_item(status="applied", backup="/b")], {}, run="earlier.json")
    plan, _ = plan_store.load_plan(str(path))
    assert plan["items"][0]["status"] == "applied" and plan["items"][0]["backup"] == "/b"


def test_save_appends_to_the_ledger_and_leaves_the_plan_file_untouched(plan_file):
    import ledger
    path = plan_file(v2_plan())
    before = path.read_bytes()
    plan, _ = plan_store.load_plan(str(path))
    plan["items"][0].update(status="applied", backup="/b", files=["/x"])
    plan["page_url"] = "https://claude.ai/artifact/abc"
    plan_store.save_plan(plan, path)
    assert path.read_bytes() == before
    assert ledger.load_state()[ledger.fingerprint(v2_item())]["status"] == "applied"
    assert ledger.page_url() == "https://claude.ai/artifact/abc"
    assert stat.S_IMODE(os.stat(ledger.ledger_path()).st_mode) == 0o600
    plan2, _ = plan_store.load_plan(str(path))
    assert plan2["items"][0]["files"] == ["/x"] and plan2["page_url"] == "https://claude.ai/artifact/abc"


def test_first_load_bootstraps_the_ledger_from_legacy_plans_and_drops_latest(plan_file):
    import ledger
    old = plan_file(v2_plan(v2_item(status="applied", backup="/b")), "old.json")
    (old.parent / "latest.json").symlink_to(old)
    newer = v2_plan()
    newer["generated"] = "2099-01-01T00:00:00"
    new = plan_file(newer, "new.json")
    plan, loaded = plan_store.load_plan(None)
    assert loaded == new and plan["items"][0]["status"] == "applied"
    assert ledger.ledger_path().exists() and not (old.parent / "latest.json").exists()


def test_rewrite_plan_is_atomic_and_0600(plan_file):
    path = plan_file(v2_plan())
    plan = json.loads(path.read_text())
    plan["summary"] = "migrated"
    plan_store.rewrite_plan(plan, path)
    assert json.loads(path.read_text())["summary"] == "migrated"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert [p for p in os.listdir(path.parent) if p.endswith(".tmp")] == []


def test_locked_blocks_second_holder(tmp_home):
    with plan_store.locked():
        fd = os.open(plan_store.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        with pytest.raises(BlockingIOError):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.close(fd)


def test_render_after_change_overlays_ledger_state(plan_file):
    import ledger
    import render
    path = plan_file(v2_plan(), "real.json")
    ledger.record([v2_item(status="applied", backup="/b")], {}, run="r")
    html = render.render_after_change(path)
    assert html.name == "real.json.html" and (path.parent / "real.json.md").exists()
    assert '"status": "applied"' in html.read_text()
