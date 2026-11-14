# cctune

Tune your Claude Code setup from your own transcripts.

`/cctune` reads the last 30 days of your Claude Code sessions, your settings, hooks, plugins,
skills and CLAUDE.md files, checks each finding against the official docs, and writes a ranked
plan. `/cctune-apply` applies the items you pick, one at a time, with a diff preview, a digest
that stops blind overwrites, a backup per item and a one-command rollback. Neither skill prints
a secret value. The audit changes nothing.

Built and tested on one heavy setup: over 1,000 sessions, 8.7 GB of transcripts, 339 installed skills,
21 plugins. The first run found three API tokens stored as literals in `settings.json`, 42 stale
project entries in `~/.claude.json`, 103 skills never invoked in 30 days, and a compaction
window set near 1M tokens. The plan it wrote had 58 items.

## Install

```
/plugin marketplace add HT-Moh/cctune
/plugin install cctune@cctune
```

Or clone and symlink both skills (see `skills/cctune/README.md`). Restart Claude Code. Needs
Python 3.10+, `jq`, `curl`, and `gh` for the quality angle.

## Use

```
/cctune                      # 30 days, your five busiest projects
/cctune 14                   # 14 days
/cctune 30 project_a,project_b cost  # two projects, one focus (cost, speed, quality, security, prompting, automation)
/cctune 30 "" prompting     # default projects, one focus; the focus is the third argument
```

The run launches eleven read-only agents plus an adversarial review and costs roughly 650k to 1M
tokens for a heavy user. You get a plan at `~/.claude/tune/plans/<date>-<id>.json`, a Markdown
report and an HTML checklist page published as an Artifact. Plans are immutable proposals; what
you applied, did or dismissed lives in `~/.claude/tune/ledger.jsonl`, keyed by the change itself,
so the next audit shows it as settled and the page keeps one URL. Then:

```
/cctune-apply                     # the plan as a table
/cctune-apply --dry-run safe      # diff of every low-risk item
/cctune-apply P1-01 P1-03         # apply two items (preview first, then with the digest it prints)
/cctune-apply --explain P0-02     # why, evidence, who reads the value, step-by-step commands
/cctune-apply --done P0-02        # record a manual item as done
/cctune-apply --rollback P1-03    # restore from that item's backup
/cctune-apply --dismiss P2-04 --reason "cron prunes these"   # never propose it again
/cctune-apply --history           # everything earlier plans settled
```

## What it finds

Every finding carries a count, a path and the method that produced it. Headless, interactive and
subagent sessions are counted apart, because they answer different questions.

- **Secrets and exposure.** Tokens stored as literals in `settings.json` env, `~/.claude.json`
  MCP config or `~/.zshrc`; credential files read by sessions; committed `.env` files; loose file
  modes on keys. The plan orders the fix so nothing breaks: move values to a 600 file first,
  rotate second, delete the literals third.
- **Cost.** First-request token size per session (median and p90), compaction frequency and
  size, instruction-file token load, skills whose descriptions sit in every turn but never fire,
  plugins with zero use, subagents that run on a larger model than their job needs.
- **Speed.** Bash commands over 120 s, wait loops, permission denials and the rules that would
  pre-approve them, blocking hooks and what they cost per call.
- **Quality.** Reverts, file churn, duplicate reads, "done" claims with no verification step,
  dangerous command forms, Write/Edit ratio, how often you type "continue" or "proceed".
- **Prompts you keep typing.** The same prompt across 3+ sessions, near-duplicate clusters, and
  3-step tool sequences you run by hand. Each becomes a proposed skill, a `$ARGUMENTS` skill or a
  CLAUDE.md line, with redacted sample prompts as evidence.
- **Coverage.** Every installed skill, MCP server and agent against what sessions invoked: the
  skills a prompt matched but never fired, the servers configured but never called.
- **Config drift.** Dangling symlinks, missing imports in CLAUDE.md, statusLine scripts that no
  longer exist, project entries whose paths are gone.

## How it works

```
~/.claude/projects/**/*.jsonl ─┐
~/.claude/settings.json        ├─ scripts/scan.py, inventory.sh ─► scan.json
~/.claude.json, plugins, skills┘                                       │
                                                                       ▼
official docs (fetched) ──► 10 analysis agents + adversarial pass ──► plan.json
                                                                       │
                                        /cctune-apply ◄── plan.md, plan.html (Artifact)
```

- `skills/cctune/scripts/` streams transcripts line by line (files reach 700 MB), never loads one
  whole. `reference/schema.md` documents every signal; `reference/briefs.md` holds the agent
  briefs; `reference/traps.md` lists the mistakes earlier audits made so the next run checks
  against them.
- `plan.json` is the single source of truth (`reference/plan.md`). Every item has a phase, a risk
  (`safe`, `review`, `manual`), evidence, a docs URL or an `UNVERIFIED` mark, `depends_on`,
  `consumers`, checks, and ops a script can execute: `json_set`, `json_delete`, `json_append`,
  `json_upsert`, `file_create`, `file_append`, `file_replace`, `symlink`, `file_remove`, or
  `manual` with numbered steps and exact commands.
- `skills/cctune-apply/scripts/apply.py` is the only thing that writes. It refuses an item whose
  dependencies are not done, refuses paths outside the allowed roots, binds every apply to the
  digest of the preview you read, keeps a backup per item, and redacts anything that looks like
  a secret in its output.

## Contributing

Issues and pull requests are welcome. The bar:

- `python3 -m pytest -q` green (462 tests) and `ruff check skills tests` clean. CI runs both on
  Python 3.10 and 3.12.
- Files under 300 lines, functions under 30, one concern per commit.
- A bug fix comes with the test that failed before it.
- Nothing in the repo prints or stores a secret value. Key names and paths only.

Good first contributions: a new structural pattern in `scan_patterns.py`, `scan_quality.py` or
`scan_turns.py` with its test, a new op
kind in `cctune-apply/scripts/ops_*.py`, a trap you hit added to `reference/traps.md`, or a run
on your own setup with the findings that were wrong.

## License

MIT
