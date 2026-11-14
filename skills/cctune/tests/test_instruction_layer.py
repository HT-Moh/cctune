"""`instruction_layer.py` counts rules, emphasis and the test command in the loaded instruction files."""
import json

import instruction_layer


def _home(tmp_path):
    claude = tmp_path / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "CLAUDE.md").write_text("@RTK.md\n\n@rules/development.md\n\n# How to answer\n\n- Use plain English.\n- Never write IMPORTANT in caps.\n"
                                      "Always name the file. Some prose that is not a rule here.\n1. Run the tests.\n")
    (claude / "RTK.md").write_text("# RTK\n\n```bash\nrtk gain\n```\n\nAll other commands are rewritten by the hook.\n")
    (claude / "rules" / "development.md").write_text("# Dev\n\n- Keep files under 300 lines.\n- Keep tests green. Run pytest before done.\n"
                                                      "- Do not THINK HARD or ultrathink, be thorough.\n")
    return tmp_path


def test_imports_resolve_once_and_files_are_listed_in_load_order(tmp_path):
    rows = instruction_layer.global_layer(_home(tmp_path))
    assert [r["file"] for r in rows] == ["~/.claude/CLAUDE.md", "~/.claude/RTK.md", "~/.claude/rules/development.md"]


def test_instruction_lines_are_bullets_numbered_and_imperative_openers():
    text = "# H\n\n- Use plain English.\n* Never shout.\n1. Run tests.\nAlways name the file. Prose after it.\nThis sentence is prose.\n\n```bash\nrtk gain\n```\n"
    assert instruction_layer.count_instructions(text) == 4


def test_emphasis_hits_count_caps_words_and_effort_phrases():
    text = "IMPORTANT: never do X. Use CLAUDE.md and the API. THINK HARD, ultrathink, be thorough, don't be lazy, keep going."
    assert instruction_layer.count_emphasis(text) == 6


def test_test_command_detection():
    assert instruction_layer.names_test_command("Run `python3 -m pytest -q tests` before committing.")
    assert instruction_layer.names_test_command("npm test and eslint must pass")
    assert not instruction_layer.names_test_command("Keep the suite green. Tests matter.")


def test_totals_and_flag_over_100_rules(tmp_path):
    home = _home(tmp_path)
    (home / ".claude" / "rules" / "many.md").write_text("".join(f"- rule number {i}\n" for i in range(120)))
    report = instruction_layer.report(home, project=None)
    assert report["totals"]["instructions"] >= 120 and report["totals"]["flag"] == "over 100 instructions: compliance drops"
    assert report["totals"]["tokens"] > 0 and report["project"] is None


def test_project_rows_and_missing_test_command(tmp_path):
    home = _home(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("- Keep it small.\n")
    (repo / ".claude" / "rules" / "api.md").write_text("- Validate inputs.\n")
    report = instruction_layer.report(home, project=repo)
    assert [r["file"] for r in report["project"]["files"]] == ["CLAUDE.md", ".claude/rules/api.md"]
    assert report["project"]["names_test_command"] is False


def test_main_prints_json_with_no_rule_text(tmp_path, capsys):
    instruction_layer.main(["--home", str(_home(tmp_path))])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["totals"]["files"] == 3 and "plain English" not in out


def test_functions_are_short():
    import inspect
    for name, fn in inspect.getmembers(instruction_layer, inspect.isfunction):
        assert len(inspect.getsource(fn).splitlines()) <= 30, name


def test_symlinked_rule_file_is_shown_by_its_link_path(tmp_path):
    home = _home(tmp_path)
    target = tmp_path / "elsewhere" / "charter.md"
    target.parent.mkdir()
    target.write_text("- Validate inputs.\n")
    (home / ".claude" / "rules" / "linked.md").symlink_to(target)
    rows = instruction_layer.global_layer(home)
    assert "~/.claude/rules/linked.md" in [r["file"] for r in rows]
    assert not any(".." in r["file"] for r in rows)
