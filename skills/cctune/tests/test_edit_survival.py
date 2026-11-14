"""`edit_survival.py`: share of lines an agent added that the next commit still carries."""
import json
import subprocess

import edit_survival

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


def _git(repo, *args, date="2099-01-01T01:00:00+00:00"):
    env = {**ENV, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "HOME": str(repo)}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _edit(uid, path, old, new, ts="2099-01-01T00:30:00Z"):
    return {"type": "assistant", "timestamp": ts, "message": {"id": uid, "content": [
        {"type": "tool_use", "id": uid, "name": "Edit", "input": {"file_path": path, "old_string": old, "new_string": new}}]}}


def _write(uid, path, content, ts="2099-01-01T00:30:00Z"):
    return {"type": "assistant", "timestamp": ts, "message": {"id": uid, "content": [
        {"type": "tool_use", "id": uid, "name": "Write", "input": {"file_path": path, "content": content}}]}}


def _setup(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.py").write_text("def keep_me():\n    return 1\n")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "base", date="2099-01-01T00:00:00+00:00")
    return repo


def test_added_lines_are_new_string_minus_old_string_minus_short_lines():
    block = {"old_string": "x = 1\n", "new_string": "x = 1\ncompute_total(rows)\nok\n\n"}
    assert edit_survival.added_lines("Edit", block) == {"compute_total(rows)"}
    assert edit_survival.added_lines("Write", {"content": "import os\nshort\n"}) == {"import os"}


def test_survival_share_against_the_next_commit(tmp_path):
    repo = _setup(tmp_path)
    events = [_edit("e1", str(repo / "a.py"), "    return 1\n", "    return 1\nsurvives_here = True\ndropped_line = 2\n"),
              _write("w1", str(repo / "b.py"), "brand_new_file = 1\nalso_dropped = 2\n")]
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (repo / "a.py").write_text("def keep_me():\n    return 1\nsurvives_here = True\n")
    (repo / "b.py").write_text("brand_new_file = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "human review")
    result = edit_survival.survival(str(f), str(repo), days=7)
    assert result == {"files": 2, "files_without_commit": 0, "lines_added": 4, "lines_surviving": 2, "survival": 0.5}


def test_file_with_no_later_commit_is_counted_apart(tmp_path):
    repo = _setup(tmp_path)
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(_edit("e1", str(repo / "a.py"), "", "never_committed = 1\n")) + "\n")
    result = edit_survival.survival(str(f), str(repo), days=7)
    assert result["files_without_commit"] == 1 and result["lines_added"] == 1 and result["lines_surviving"] == 0


def test_edits_outside_the_repo_are_ignored(tmp_path):
    repo = _setup(tmp_path)
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(_edit("e1", "/elsewhere/a.py", "", "elsewhere_line = 1\n")) + "\n")
    assert edit_survival.survival(str(f), str(repo), days=7)["files"] == 0


def test_main_prints_json_without_content(tmp_path, capsys):
    repo = _setup(tmp_path)
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(_edit("e1", str(repo / "a.py"), "", "secret_token_line = 1\n")) + "\n")
    edit_survival.main(["--session", str(f), "--repo", str(repo)])
    out = capsys.readouterr().out
    assert json.loads(out)["files"] == 1 and "secret_token_line" not in out


def test_functions_are_short():
    import inspect
    for name, fn in inspect.getmembers(edit_survival, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name
