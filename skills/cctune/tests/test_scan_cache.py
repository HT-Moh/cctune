"""Per-transcript cache: a scanned file is summarised once and merged on later runs."""
import json
import os
import stat
import time

import scan_cache
import scan_coverage
import scan_lib
from test_scan_patterns import assistant_text, bash, tool_result, tool_use, user_text

INVENTORY = {"skills": [{"name": "deploy", "terms": ["deploy", "release", "ship it", "production"]}],
             "mcp_servers": [{"name": "firecrawl"}, {"name": "github"}]}
USAGE = {"input_tokens": 100, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 200, "output_tokens": 10}


def _events(tag):
    a, b, c, d = (f"{x}-{tag}" for x in "abcd")
    return [user_text(f"deploy the release to production now, ship it {tag}", 0),
            tool_use(a, "Read", {"file_path": "/r/x.py"}, 1, usage=USAGE), tool_result(a, "x" * 30000, 2),
            tool_use(b, "Read", {"file_path": "/r/x.py"}, 3), tool_result(b, "x", 4),
            bash(c, "pytest -q", 5), tool_result(c, "ok", 6), tool_use(d, "mcp__firecrawl__scrape", {}, 7),
            tool_result(d, "ok", 8), user_text("continue", 9), assistant_text("tests pass now", 10, msg_id=f"t-{tag}")]


def _write(tmp_path, rel, events):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return str(f)


def _index():
    return scan_coverage.Index(INVENTORY)


def _summary(pop):
    import scan
    return json.loads(json.dumps(scan.population_summary(pop)))


def test_merged_records_equal_one_direct_scan(tmp_path):
    files = [_write(tmp_path, f"p/{n}.jsonl", _events(n)) for n in ("one", "two", "three")]
    direct = scan_lib.Pop(_index())
    for f in files:
        scan_lib.scan_file(f, lambda e, p: direct, 10 ** 9, cutoff=0)
    merged = scan_lib.Pop(_index())
    for f in files:
        name, status, pop = scan_cache.scan_one(f, _index(), 10 ** 9, cutoff=0)
        assert (name, status) == ("interactive", "ok")
        scan_cache.merge_into(merged, json.loads(json.dumps(scan_cache.encode(pop))))
    assert _summary(merged) == _summary(direct)
    assert _summary(merged)["mcp_servers_used"] == {"firecrawl": 3}
    assert _summary(merged)["patterns"]["nudge_prompts"] == 3


def test_encode_leaves_out_index_message_ids_and_private_state(tmp_path):
    f = _write(tmp_path, "p/one.jsonl", _events("one"))
    _, _, pop = scan_cache.scan_one(f, _index(), 10 ** 9, cutoff=0)
    data = scan_cache.encode(pop)
    assert "msg_ids" not in data and "index" not in data["coverage"]
    assert not any(k.startswith("_") for k in data["coverage"]) and "line" not in data["coverage"]


def test_capped_lists_stay_capped_after_merge(tmp_path):
    merged = scan_lib.Pop(_index())
    for n in range(8):
        f = _write(tmp_path, f"p/s{n}.jsonl", [user_text("run the deploy to production and ship it", 0)] * 2)
        _, _, pop = scan_cache.scan_one(f, _index(), 10 ** 9, cutoff=0)
        scan_cache.merge_into(merged, scan_cache.encode(pop))
    summary = _summary(merged)
    assert summary["repeated_prompts"][0]["sessions"] == 8 and len(summary["repeated_prompts"][0]["files"]) == 5
    assert summary["missed_skill_sessions"][0]["sessions"] == 8 and len(summary["missed_skill_sessions"][0]["locations"]) == 5


def test_population_of_uses_entrypoint_and_subagent_path():
    assert scan_cache.population_of("cli", "/p/a.jsonl") == "interactive"
    assert scan_cache.population_of("", "/p/a.jsonl") == "interactive"
    assert scan_cache.population_of("sdk-py", "/p/a.jsonl") == "headless"
    assert scan_cache.population_of("cli", "/p/a/subagents/agent-1.jsonl") == "subagent"


def test_lookup_misses_until_stored_and_after_the_file_changes(tmp_path):
    f = _write(tmp_path, "p/one.jsonl", _events("one"))
    cache = scan_cache.Cache(str(tmp_path / "cache"), "v1")
    assert cache.lookup(f, cutoff=0) is None
    record = scan_cache.record_for(f, "interactive", "ok", scan_lib.Pop(), cutoff=0)
    assert cache.store(f, record)
    assert cache.lookup(f, cutoff=0)["population"] == "interactive"
    assert scan_cache.Cache(str(tmp_path / "cache"), "v2").lookup(f, cutoff=0) is None
    with open(f, "a") as fh:
        fh.write(json.dumps(user_text("more", 11)) + "\n")
    assert cache.lookup(f, cutoff=0) is None


def test_record_is_reused_across_windows_only_when_complete(tmp_path):
    f = _write(tmp_path, "p/one.jsonl", _events("one"))
    first_ts = scan_lib.ts("2099-01-01T00:00:00Z")
    cache = scan_cache.Cache(str(tmp_path / "cache"), "v1")
    cache.store(f, scan_cache.record_for(f, "interactive", "ok", scan_lib.Pop(), cutoff=first_ts - 10))
    assert cache.lookup(f, cutoff=first_ts - 10 ** 6) is not None
    assert cache.lookup(f, cutoff=first_ts + 60) is None
    cache.store(f, scan_cache.record_for(f, "interactive", "ok", scan_lib.Pop(), cutoff=first_ts + 60))
    assert cache.lookup(f, cutoff=first_ts + 90) is not None
    assert cache.lookup(f, cutoff=first_ts - 10) is None


def test_store_is_owner_only_and_refuses_a_secret(tmp_path):
    f = _write(tmp_path, "p/one.jsonl", _events("one"))
    cache = scan_cache.Cache(str(tmp_path / "cache"), "v1")
    cache.store(f, scan_cache.record_for(f, "interactive", "ok", scan_lib.Pop(), cutoff=0))
    paths = [os.path.join(cache.directory, n) for n in os.listdir(cache.directory)]
    assert len(paths) == 1 and stat.S_IMODE(os.stat(paths[0]).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(cache.directory).st_mode) == 0o700
    bad = scan_lib.Pop()
    bad.reasons["token sk_live_abcdef0123456789"] += 1
    assert not cache.store(f, scan_cache.record_for(f, "interactive", "ok", bad, cutoff=0))
    assert len(os.listdir(cache.directory)) == 1


def test_prune_removes_records_older_than_the_limit(tmp_path):
    cache = scan_cache.Cache(str(tmp_path / "cache"), "v1")
    for n in ("a", "b"):
        f = _write(tmp_path, f"p/{n}.jsonl", _events(n))
        cache.store(f, scan_cache.record_for(f, "interactive", "ok", scan_lib.Pop(), cutoff=0))
    old = os.path.join(cache.directory, sorted(os.listdir(cache.directory))[0])
    os.utime(old, (time.time() - 100 * 86400,) * 2)
    assert cache.prune(max_age_days=90) == 1 and len(os.listdir(cache.directory)) == 1


def test_scanner_version_follows_source_and_inventory(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "scan_x.py").write_text("a = 1\n")
    inventory = tmp_path / "inventory.json"
    inventory.write_text("{}")
    v1 = scan_cache.scanner_version(str(scripts), str(inventory))
    (scripts / "scan_x.py").write_text("a = 2\n")
    v2 = scan_cache.scanner_version(str(scripts), str(inventory))
    inventory.write_text("{\"skills\": []}")
    v3 = scan_cache.scanner_version(str(scripts), str(inventory))
    assert len({v1, v2, v3}) == 3 and len(v1) == 16
    assert scan_cache.scanner_version(str(scripts), "") != v3


def _run_scan(monkeypatch, tmp_path, out_name, extra=()):
    import scan
    monkeypatch.setattr(scan, "ROOT", str(tmp_path / "projects"))
    out = tmp_path / out_name
    argv = ["scan.py", "--days", "100000", "--out", str(out), "--cache-dir", str(tmp_path / "cache"), *extra]
    monkeypatch.setattr("sys.argv", argv)
    scan.main()
    return json.loads(out.read_text())


def test_second_run_reads_from_the_cache_and_matches_the_first(monkeypatch, tmp_path, capsys):
    _write(tmp_path, "projects/-p/one.jsonl", _events("one"))
    _write(tmp_path, "projects/-p/one/subagents/agent-1.jsonl", _events("sub"))
    first = _run_scan(monkeypatch, tmp_path, "first.json")
    assert "cache: hits=0 misses=2" in capsys.readouterr().err
    _write(tmp_path, "projects/-p/two.jsonl", _events("two"))
    second = _run_scan(monkeypatch, tmp_path, "second.json")
    assert "cache: hits=2 misses=1" in capsys.readouterr().err
    assert second["interactive"]["sessions"] == 2 and second["subagent"]["sessions"] == 1
    assert first["subagent"] == second["subagent"]
    third = _run_scan(monkeypatch, tmp_path, "third.json", ["--no-cache"])
    assert "cache:" not in capsys.readouterr().err
    assert third == second
