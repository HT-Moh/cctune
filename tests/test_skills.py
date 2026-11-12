"""Shape of every skill folder: frontmatter, README, evals, plugin manifest."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(ROOT.glob("skills/*/SKILL.md"))
IDS = [p.parent.name for p in SKILLS]
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8").split("---\n", 2)[1]
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith("  ") and key:
            out[key] = (out[key] + " " + line.strip()).strip()
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        out[key] = "" if value.strip() in (">-", "") else value.strip()
    return out


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_name_matches_folder(skill):
    assert frontmatter(skill)["name"] == skill.parent.name


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_skill_is_user_invoked(skill):
    assert frontmatter(skill).get("disable-model-invocation") == "true"


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_readme_has_install_section(skill):
    assert "## Install" in (skill.parent / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_evals_have_three_checkable_cases(skill):
    evals = json.loads((skill.parent / "evals" / "evals.json").read_text(encoding="utf-8"))
    assert len(evals["evals"]) >= 3
    for case in evals["evals"]:
        assert case["prompt"].strip() and len(case["expectations"]) >= 3, case["id"]


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_plugin_manifest_lists_skill(skill):
    assert f"./skills/{skill.parent.name}" in PLUGIN["skills"]


def test_plugin_manifest_lists_only_existing_skills():
    assert sorted(PLUGIN["skills"]) == sorted(f"./skills/{p.parent.name}" for p in SKILLS)
