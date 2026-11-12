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

Install the plugin (both skills ship together):

```
/plugin marketplace add HT-Moh/cctune
/plugin install cctune@cctune
```

Or clone and link, which keeps `git pull` as the update path:

```bash
git clone https://github.com/HT-Moh/cctune.git ~/src/cctune
ln -s ~/src/cctune/skills/cctune ~/.claude/skills/cctune
ln -s ~/src/cctune/skills/cctune-apply ~/.claude/skills/cctune-apply
```

Restart Claude Code after either. The two skills import from each other, so keep them side
by side.

Requirements: Python 3.10+. Tests: `python3 -m pytest -q skills/cctune-apply` from the repo
root.
