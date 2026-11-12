# cctune-apply

Applies items from the latest `cctune` plan. Every item is previewed first as a diff, the
preview prints a digest, and the apply command carries that digest so a changed file is never
overwritten blind. Each applied item gets its own backup directory and rolls back on its own.
Items marked `review` are confirmed one by one; `manual` items are printed with the exact command
and recorded with `--done` once you have done them. The script never prints a secret value.

## Usage

```
/cctune-apply                    # show the plan table
/cctune-apply --dry-run safe     # preview every safe item
/cctune-apply P1-01 P1-03        # preview, then apply with the digest it prints
/cctune-apply --explain P1-08    # why, consumers, dependencies
/cctune-apply --rollback P1-03
/cctune-apply --done P0-01       # record a manual item
```

Selection tokens: an id (`P1-02`), a phase (`phase1`), `safe`, or `all`.

## Install

Install together with `cctune`, which imports `scripts/redact.py` from this folder. Clone
once, link both, restart Claude Code:

```bash
git clone https://github.com/HT-Moh/skills.git ~/src/skills
ln -s ~/src/skills/engineering/cctune ~/.claude/skills/cctune
ln -s ~/src/skills/engineering/cctune-apply ~/.claude/skills/cctune-apply
```

A symlink keeps `git pull` as the update path. Copying works too (`cp -r` both folders into
`~/.claude/skills/`), but then updates are manual.

Requirements: Python 3.10+. Tests: `python3 -m pytest -q engineering/cctune-apply` from the
repo root.
