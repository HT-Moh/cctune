"""A fingerprint names the change an item makes, stable across runs, ids and rewordings."""
import plan_fingerprint as fp


def item(ops, **over):
    base = {"id": "P1-01", "title": "t", "risk": "safe", "ops": ops}
    base.update(over)
    return base


def test_same_json_change_different_id_title_and_value_shares_a_fingerprint(monkeypatch):
    monkeypatch.setenv("HOME", "/home/u")
    a = item([{"kind": "json_set", "file": "~/.claude/settings.json", "path": ["autoCompactWindow"], "value": 400000}])
    b = item([{"kind": "json_set", "file": "/home/u/.claude/settings.json", "path": ["autoCompactWindow"], "value": 300000}],
             id="P2-07", title="Compact earlier")
    assert fp.fingerprint(a) == fp.fingerprint(b) and len(fp.fingerprint(a)) == 16


def test_different_path_or_kind_differs():
    a = item([{"kind": "json_set", "file": "~/.claude/settings.json", "path": ["autoCompactWindow"], "value": 1}])
    b = item([{"kind": "json_delete", "file": "~/.claude/settings.json", "path": ["autoCompactWindow"]}])
    c = item([{"kind": "json_set", "file": "~/.claude/settings.json", "path": ["env", "X"], "value": 1}])
    assert len({fp.fingerprint(a), fp.fingerprint(b), fp.fingerprint(c)}) == 3


def test_text_ops_ignore_case_whitespace_and_punctuation():
    a = item([{"kind": "file_append", "file": "~/.claude/CLAUDE.md", "content": "Run the tests first.\n"}])
    b = item([{"kind": "file_append", "file": "~/.claude/CLAUDE.md", "content": "  run   the tests FIRST "}])
    c = item([{"kind": "file_append", "file": "~/.claude/CLAUDE.md", "content": "Run the linter first."}])
    assert fp.fingerprint(a) == fp.fingerprint(b) != fp.fingerprint(c)


def test_manual_item_keyed_by_its_steps_commands_before_text():
    a = item([{"kind": "manual", "text": "Rotate the key", "steps": [{"text": "x", "code": "claude mcp remove firecrawl"}]}], risk="manual")
    b = item([{"kind": "manual", "text": "Rotate the Firecrawl key at the provider", "steps": [{"text": "y", "code": "claude mcp remove firecrawl"}]}], risk="manual")
    c = item([{"kind": "manual", "text": "Rotate the key"}], risk="manual")
    assert fp.fingerprint(a) == fp.fingerprint(b) != fp.fingerprint(c)


def test_home_directory_is_normalised_to_tilde(monkeypatch):
    monkeypatch.setenv("HOME", "/home/alice")
    assert fp.normal_file("/home/alice/.claude/settings.json") == "~/.claude/settings.json"
    assert fp.normal_file("~/.claude/settings.json") == "~/.claude/settings.json"
    assert fp.normal_file("/etc/x") == "/etc/x"


def test_symlink_and_remove_ops():
    a = item([{"kind": "symlink", "link": "~/.claude/skills/x", "target": "../../.agents/skills/x"}])
    b = item([{"kind": "file_remove", "file": "~/.claude/settings.json.bak"}])
    assert fp.fingerprint(a) != fp.fingerprint(b)


def test_functions_are_short():
    import inspect
    for name, fn in inspect.getmembers(fp, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name
