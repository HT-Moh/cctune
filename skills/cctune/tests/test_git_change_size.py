"""`git_change_size.py` reports lines changed per commit against the review-size bands."""
import json
import subprocess
from pathlib import Path

import git_change_size

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "git_change_size.py"


def _git(repo, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
           "GIT_AUTHOR_DATE": "2099-01-01T00:00:00", "GIT_COMMITTER_DATE": "2099-01-01T00:00:00", "HOME": str(repo)}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _commit(repo, name, lines):
    (repo / name).write_text("".join(f"line {i}\n" for i in range(lines)))
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"add {name}")


def _repo(tmp_path, sizes):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    for i, n in enumerate(sizes):
        _commit(repo, f"f{i}.txt", n)
    return repo


def test_stats_percentiles_and_band_shares(tmp_path):
    repo = _repo(tmp_path, [10, 50, 84, 100, 300])
    stats = git_change_size.repo_stats(str(repo), since="2000-01-01")
    assert stats["commits"] == 5 and stats["lines_p50"] == 84 and stats["lines_p90"] == 300
    assert stats["share_under_85"] == 0.6 and stats["share_over_209"] == 0.2


def test_binary_and_lockfile_rows_are_skipped():
    numstat = "12\t3\tsrc/a.py\n-\t-\timg.png\n900\t0\tpackage-lock.json\n5\t5\tuv.lock\n"
    assert git_change_size.parse_numstat(numstat) == 15


def test_main_prints_one_row_per_repo_and_a_flag(tmp_path, capsys):
    repo = _repo(tmp_path, [250, 300])
    git_change_size.main(["--repos", str(repo), "--since", "2000-01-01"])
    out = capsys.readouterr().out
    row = json.loads(out.splitlines()[0])
    assert row["repo"] == "r" and row["commits"] == 2 and row["flag"] == "p50 above 209: split the work"
    assert "300" in out


def test_missing_repo_is_reported_not_raised(tmp_path, capsys):
    git_change_size.main(["--repos", str(tmp_path / "nope"), "--since", "2000-01-01"])
    assert "not a git repo" in capsys.readouterr().out


def test_functions_are_short():
    import inspect
    for name, fn in inspect.getmembers(git_change_size, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name
