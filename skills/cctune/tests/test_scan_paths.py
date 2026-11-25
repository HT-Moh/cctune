"""Files touched outside the session's working directory: the `additionalDirectories` signal."""
import json

import scan_lib
import scan_paths
from test_scan_patterns import bash, tool_result, tool_use, user_text


def _scan(tmp_path, events, name="s.jsonl", pop=None, cwd="/r/app"):
    for ev in events:
        ev.setdefault("cwd", cwd)
    f = tmp_path / name
    f.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    pop = pop or scan_lib.Pop()
    scan_lib.scan_file(str(f), lambda e, p: pop, 10 ** 9, cutoff=0)
    return pop


def test_outside_paths_counted_per_call_and_per_session(tmp_path):
    pop = _scan(tmp_path, [user_text("go"), tool_use("a", "Read", {"file_path": "/r/app/src/x.py"}),
                           tool_use("b", "Read", {"file_path": "/r/other/README.md"}),
                           tool_use("c", "Edit", {"file_path": "/r/other/src/y.py"}),
                           tool_use("d", "Grep", {"pattern": "x", "path": "/r/third"}),
                           tool_use("e", "Write", {"file_path": "/r/app/notes.md"})])
    summary = scan_paths.summary(pop.patterns.paths)
    assert summary == {"calls_outside_cwd": 3, "sessions_outside_cwd": 1, "outside_dirs_distinct": 3}


def test_scratch_home_claude_relative_and_cwd_itself_are_not_outside(tmp_path):
    pop = _scan(tmp_path, [tool_use("a", "Read", {"file_path": "/tmp/claude-1000/x/scratchpad/n.txt"}),
                           tool_use("b", "Read", {"file_path": "/home/u/.claude/settings.json"}),
                           tool_use("c", "Read", {"file_path": "src/x.py"}),
                           tool_use("d", "Read", {"file_path": "/r/app"}),
                           tool_use("e", "Read", {"file_path": "/r/application/x.py"})], cwd="/r/app")
    assert scan_paths.summary(pop.patterns.paths) == {"calls_outside_cwd": 1, "sessions_outside_cwd": 1,
                                                       "outside_dirs_distinct": 1}


def test_without_a_cwd_nothing_is_outside(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps(tool_use("a", "Read", {"file_path": "/r/other/x.py"})) + "\n")
    pop = scan_lib.Pop()
    scan_lib.scan_file(str(f), lambda e, p: pop, 10 ** 9, cutoff=0)
    assert scan_paths.summary(pop.patterns.paths)["calls_outside_cwd"] == 0


def test_sessions_and_distinct_dirs_accumulate_across_files(tmp_path):
    pop = _scan(tmp_path, [tool_use("a", "Read", {"file_path": "/r/other/x.py"})], "a.jsonl")
    _scan(tmp_path, [tool_use("a", "Read", {"file_path": "/r/other/x.py"}), bash("b", "ls"), tool_result("b")], "b.jsonl", pop)
    _scan(tmp_path, [tool_use("a", "Read", {"file_path": "/r/app/x.py"})], "c.jsonl", pop)
    assert scan_paths.summary(pop.patterns.paths) == {"calls_outside_cwd": 2, "sessions_outside_cwd": 2,
                                                       "outside_dirs_distinct": 1}


def test_patterns_summary_carries_the_three_keys(tmp_path):
    import scan_patterns
    pop = _scan(tmp_path, [tool_use("a", "Read", {"file_path": "/r/other/x.py"})])
    summary = scan_patterns.summary(pop.patterns, 1)
    assert summary["calls_outside_cwd"] == 1 and summary["sessions_outside_cwd"] == 1
    assert summary["outside_dirs_distinct"] == 1
