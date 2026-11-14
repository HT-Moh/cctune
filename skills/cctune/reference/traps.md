# Traps seen in earlier audits. Check each one before reporting.

Measurement artefacts
- "Reviews never lead to edits": parents that orchestrate never edit; the fixer
  subagents do. Count edits by later agents on files the review named.
- "Git is slow": the long calls were `git pull && until gh run ...` CI loops and
  `git add && pytest` chains. Measure the bare command before blaming it.
- "30% of PRs need rework": builders split initial work into several `fix:` commits.
  Classify each fix commit's cause before counting it as rework.
- Durations include permission-prompt wait. Say so.
- A one-shot plugin session (security review per change) can look like interactive
  work. Separate it by its identical first prompt.
- Pattern counters are hints, not findings. `done_without_verify` matches prose about
  tests, not only claims; `repeated_bash` in subagents is mostly legitimate re-runs after
  an edit; `tool_wait` on AskUserQuestion, Agent and Workflow is the user or the agent
  working, not permission wait; `reverts` in subagents include worktree setup. Read
  samples before turning a count into an item.
- Revert rate as a quality signal: agent commits are reverted at 1.1% against 1.6% for
  human ones. `reverts` is descriptive; quality lives in survival and change size.
- Idle gaps are review or absence, not "think time"; the median gap across sessions is
  about 25 min, so a 30-min cut drops half the data. Report the distribution.
- `/loop`, a ralph loop or an "always continue" rule as the fix for nudge prompts: an
  unattended loop without a runnable check over-persists. `/goal <check>` or a Stop hook.
- A skill induced from repeated prompts must not carry a value from any sample: no path,
  branch, PR number, host or token. Replace them with `$ARGUMENTS` or a placeholder and
  state the rule in the skill body.

Config changes that backfire
- Disabling a plugin removes its agents and skills. Count their calls first; copy the
  agent files to `~/.claude/agents/` and strip references to plugin-only tools
  (`lsp_*`, `ast_grep`, `.omc/`, plugin agent names).
- `CLAUDE_CODE_SUBAGENT_MODEL` loses to agent frontmatter `model:`. Built-in agents
  take the model per call.
- A global typecheck/lint Stop hook duplicates pre-commit hooks and catches nothing
  when CI never fails on them. Tests are what fail. Any Stop hook must exit 0 fast
  when nothing changed, handle deleted files and spaces, honour `stop_hook_active`,
  and find the repo from `cwd`, not `$CLAUDE_PROJECT_DIR`.
- `cleanupPeriodDays` never deletes memory; lowering it from 10 years saves little.
- `Bash(kubectl -n * get *)`: `*` before the subcommand also matches
  `kubectl -n x delete pod get y`. One rule per namespace. `cd` is built-in; a `Cd()`
  rule switches `/cd` into allowlist mode. `/usr/bin/git` does not match `git`.
- `deny` on `kubectl * secret*` blocks `-o name` listings and pull-secret reads;
  `ask` is the right level. `cat` never prompts; protect secret files with
  `deny: Read(path)`.
- Secrets in `settings.json` `env` reach every Bash subprocess. Sourcing a secrets file
  from `.zshrc` does nothing for the desktop app, cron or `claude -p` from a
  non-login shell. Use a wrapper script as the MCP `command`, `${VAR}` in MCP config,
  `headersHelper`; delete the literals and scrub backups after rotation.
- Hand-editing `~/.claude.json` while sessions run gets overwritten; close sessions or
  use `claude mcp add/remove`.
- A memory limit on a leaking proxy turns a slow leak into a restart loop. Find the
  leak before capping.
- Compose and stack files need `$$` for a literal `$`.
- Traefik/WAF/proxy plugins removed for stability must be surfaced as a security
  tradeoff with a tracking issue and an expiry, never silently.

Instruction-layer traps
- `IMPORTANT` and capitals do not help; current models over-apply emphasis. Rules
  that must never break belong in a hook or a deny rule.
- Copies of one `RULES.md` across projects drift and contradict the global file.
- Dangling `CLAUDE.md` symlinks and 0-byte files load nothing silently.
- Rules in `.claude/rules/*.md` with `paths:` are summarised away at compaction.

Process traps
- Scratch under `/tmp` dies with a reboot; plans and state go in the repo.
- 1M-context sessions compact near 967k; `/autocompact 300k` is the largest lever on
  model time for long sessions.
- Merge only when CI is green; `gh pr checks --watch` in the background, never
  `sleep` loops.
- A manual item whose text says "use the file created by P0-02" while P0-02 depends on
  it cannot be done in either order. Put the prerequisite first (secrets file before the
  rotation, with the current values), then rotate into it. `plan_render.py` prints a
  `WARNING:` for each such pair.
- A manual `claude mcp add` step with `-e` before the server name fails with "missing
  required argument 'name'": `-e <env...>` is variadic and swallows the name. Write the
  name first, every `-e` after it, `--` before the command. Check every CLI in a manual
  step against its `--help` output from this run, not from memory.
- "Rotate the key at <vendor>.dev" is wrong when the URL key beside it points at the
  user's own host (FIRECRAWL_URL -> firecrawl.bicatalyst.ch). Resolve the host of every
  `*_URL` key before naming where a key is rotated; self-hosted means the deployment config.
- Rotation before removing the literals breaks the service: Claude Code writes
  `settings.json` `env` into its own environment and `.zshrc` exports run after a sourced
  secrets file, so the old literal wins over the rotated value. Order: secrets file and
  `${VAR}` wiring, then delete the literals, then rotate one key at a time.
