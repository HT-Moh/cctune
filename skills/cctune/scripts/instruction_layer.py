#!/usr/bin/env python3
"""Count what the loaded instruction layer asks of the model: rules, emphasis, the test command.

Resolves `~/.claude/CLAUDE.md` with its `@imports` and `~/.claude/rules/*.md` (and a project's
`CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md` with `--project`). Per file: approximate tokens,
instruction lines (bullets, numbered steps, imperative openers), emphasis hits (`IMPORTANT`,
ALL CAPS, think-hard phrases) and whether a test, lint or typecheck command is named.
Instruction-following compliance drops from 94% at 100 rules to 77% at 250; emphasis makes the
model over-apply a rule. Prints counts and paths only, never a rule's text.
Usage: instruction_layer.py [--home ~] [--project <repo>]
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from scan_quality import TEST_RE  # noqa: E402

RULE_FLAG_AT = 100
BULLET_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+\S")
IMPERATIVE_RE = re.compile(r"^(Never|Always|Do not|Don't|Use|Keep|Run|Write|Avoid|Prefer|Put|Give|Make|Report|Say|Ask|Name|"
                           r"Delete|Add|Follow|Test|Check|Treat|State|Limit|Split|Validate|Handle|Throw|Return|Measure|Assert|"
                           r"Log|Move|Set|Choose|Search|Fix|Separate|Group|Flag|Explain|Justify|List|Quote|Stop|Read|Expand|"
                           r"Answer|Apply|Commit|Leave|Replace|Call|Respond|Confirm|Mark|Only|No)\b")
EMPHASIS_RE = re.compile(r"important|think hard(er)?|ultrathink|be thorough|do(n't| not) be lazy|keep going", re.I)
CAPS_RE = re.compile(r"(?<![\w.])[A-Z]{5,}(?![\w.])")
IMPORT_RE = re.compile(r"^@(\S+)\s*$")
FENCE = "```"


def _prose_lines(text):
    """Lines outside fenced code blocks."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith(FENCE):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def count_instructions(text):
    return sum(1 for ln in _prose_lines(text) if BULLET_RE.match(ln) or IMPERATIVE_RE.match(ln.strip()))


def count_emphasis(text):
    prose = "\n".join(_prose_lines(text))
    phrases = len(EMPHASIS_RE.findall(prose))
    return phrases + len(CAPS_RE.findall(EMPHASIS_RE.sub(" ", prose)))


def names_test_command(text):
    return bool(TEST_RE.search(text))


def _row(path, shown):
    text = open(path, encoding="utf-8", errors="replace").read()
    return {"file": shown, "tokens": len(text) // 4, "instructions": count_instructions(text),
            "emphasis": count_emphasis(text), "names_test_command": names_test_command(text)}


def _with_imports(path, seen):
    """`path` then every `@import` it names, depth first, each file once (a symlink keeps its link path)."""
    real = os.path.realpath(path)
    if real in seen or not os.path.isfile(real):
        return []
    seen.add(real)
    files = [path]
    for line in _prose_lines(open(real, encoding="utf-8", errors="replace").read()):
        if m := IMPORT_RE.match(line.strip()):
            target = os.path.expanduser(m.group(1))
            files += _with_imports(target if os.path.isabs(target) else os.path.join(os.path.dirname(real), target), seen)
    return files


def _layer(entry_files, rule_glob, base):
    seen, files = set(), []
    for entry in entry_files:
        files += _with_imports(entry, seen)
    for rule in sorted(glob.glob(rule_glob)):
        files += _with_imports(rule, seen)
    return [_row(f, os.path.relpath(f, base)) for f in files]


def global_layer(home):
    claude = os.path.join(home, ".claude")
    rows = _layer([os.path.join(claude, "CLAUDE.md")], os.path.join(claude, "rules", "*.md"), home)
    for r in rows:
        r["file"] = "~/" + r["file"]
    return rows


def project_layer(repo):
    entries = [os.path.join(repo, "CLAUDE.md"), os.path.join(repo, "AGENTS.md")]
    rows = _layer(entries, os.path.join(repo, ".claude", "rules", "*.md"), repo)
    return {"files": rows, "names_test_command": any(r["names_test_command"] for r in rows)}


def report(home, project):
    rows = global_layer(home)
    instructions = sum(r["instructions"] for r in rows)
    totals = {"files": len(rows), "tokens": sum(r["tokens"] for r in rows), "instructions": instructions,
              "emphasis": sum(r["emphasis"] for r in rows),
              "flag": f"over {RULE_FLAG_AT} instructions: compliance drops" if instructions > RULE_FLAG_AT else ""}
    return {"global": rows, "totals": totals, "project": project_layer(str(project)) if project else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--home", default=os.path.expanduser("~"))
    ap.add_argument("--project", default="")
    a = ap.parse_args(argv)
    print(json.dumps(report(a.home, a.project or None), indent=1))


if __name__ == "__main__":
    sys.exit(main())
