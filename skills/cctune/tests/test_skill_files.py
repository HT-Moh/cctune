import re
import subprocess
from pathlib import Path

import pytest

ENGINEERING = Path(__file__).resolve().parents[2]
SKILLS = {"cctune": ENGINEERING / "cctune" / "SKILL.md",
          "cctune-apply": ENGINEERING / "cctune-apply" / "SKILL.md"}


def frontmatter(path: Path) -> dict:
    """Minimal YAML reader for our frontmatter: scalars, folded `>-` scalars, one nesting level."""
    text = path.read_text(encoding="utf-8")
    body = text.split("---\n", 2)[1]
    out, key, parent = {}, None, None
    for line in body.splitlines():
        if line.startswith("  ") and key:
            if parent is None:
                out[key] = (out[key] + " " + line.strip()).strip()
            else:
                k, v = line.strip().split(":", 1)
                out[f"{parent}.{k}"] = v.strip()
            continue
        k, _, v = line.partition(":")
        key, v = k.strip(), v.strip()
        parent = key if v == "" else None
        out[key] = "" if v in (">-", "") else v
    return out


@pytest.mark.parametrize("name", list(SKILLS))
def test_frontmatter_parses_and_has_required_keys(name):
    fm = frontmatter(SKILLS[name])
    assert fm["name"] == name
    assert fm["metadata.author"] == "Mohamed Habbat (https://github.com/HT-Moh)"
    assert fm["disable-model-invocation"] == "true"
    assert len(fm["description"]) <= 1536
    for dead in ("when_to_use", "context", "agent", "background"):
        assert dead not in fm, dead


@pytest.mark.parametrize("name", list(SKILLS))
def test_injected_blocks_have_no_splitters(name):
    text = SKILLS[name].read_text(encoding="utf-8")
    blocks = re.findall(r"```!\n(.*?)```", text, re.S)
    assert blocks, "each skill injects at least one command"
    for block in blocks:
        assert not re.search(r"&&|\|\||;|\||(?<!\$)&(?!&)|\n.+\n", block.strip() + "\n"), block


@pytest.mark.parametrize("name", list(SKILLS))
def test_skill_is_portable(name):
    text = SKILLS[name].read_text(encoding="utf-8")
    assert "/home/bicatalyst" not in text
    bash_rules = re.findall(r"Bash\(([^)]*)\)", frontmatter(SKILLS[name])["allowed-tools"])
    assert all("~" not in rule for rule in bash_rules)


PRIVATE_NAMES = ("valradar", "mindmeld", "bicatalyst")
PUBLIC_TEXT = [p for p in ENGINEERING.parent.rglob("*") if p.suffix in (".md", ".json") and ".omc" not in p.parts and ".git" not in p.parts]


@pytest.mark.parametrize("path", PUBLIC_TEXT, ids=lambda p: str(p.relative_to(ENGINEERING.parent)))
def test_docs_name_no_private_project(path):
    text = path.read_text(encoding="utf-8").lower()
    hits = [n for n in PRIVATE_NAMES if n in text]
    assert hits == [] or path.name == "test_skill_files.py", hits


def test_apply_read_rule_is_plans_only():
    fm = frontmatter(SKILLS["cctune-apply"])
    reads = re.findall(r"Read\(([^)]*)\)", fm["allowed-tools"])
    assert reads == ["~/.claude/tune/plans/**"]


def test_apply_procedure_uses_digest_and_confirmed():
    text = SKILLS["cctune-apply"].read_text(encoding="utf-8")
    for needle in ("--dry-run", "--expect", "--confirmed", "AskUserQuestion", "--done", "--explain", "--purge-backup"):
        assert needle in text, needle


def test_tune_procedure_waits_for_agents_and_names_splitters():
    text = SKILLS["cctune"].read_text(encoding="utf-8")
    assert "run_in_background" not in text.replace("never `run_in_background`", "")
    assert "never end the turn" in text
    for splitter in ("`&&`", "`||`", "`;`", "`|`"):
        assert splitter in text, splitter


def test_inventory_rejects_non_integer_days():
    script = ENGINEERING / "cctune" / "scripts" / "inventory.sh"
    r = subprocess.run(["bash", str(script), "abc"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "integer" in r.stdout
