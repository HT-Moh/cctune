# Agent briefs

Launch these in parallel with the Agent tool. Every brief starts with the same header:

> READ-ONLY. Do not modify any file, repo or config. Scratch only under `mktemp -d`.
> Never print secret values; report key names and file paths. Stream large files (up
> to 700 MB) with jq/python; `head -c 40000` to learn the schema. Return under 700
> words: each finding as (observation, evidence with count and path, method,
> recommendation naming the exact file/key/flag, estimated impact). Mark anything
> you could not verify. Window: `$days` days. Projects: `$projects`.

Then the angle. Paste `reference/schema.md` into each brief.

## A. Headless and pipeline runs
Population `sdk-*` plus one-shot plugin sessions. Per run: fresh tokens median/p90,
first-request size, model mix. Repeated first prompts and how many sessions each
starts. Error classes. Read the launcher code in the repo (grep `claude -p`,
`--output-format`, `--setting-sources`, `--no-session-persistence`,
`--max-budget-usd`, `--json-schema`, `--max-turns`, `--bare`) and list the flags
missing. Estimate tokens saved if the first request dropped to 15k and pair it with outcomes: per
run, OK or FAIL from the launcher's exit code or `--json-schema` output where logged, and
the count of runs that stopped on `--max-turns` or `--max-budget-usd`. Spend with no
outcome beside it is not a finding.

## B. Interactive workflow
Population `cli` with 4+ real user messages. Time from each request to the next
user message by task type (deploy, CI fix, refactor, content, debugging, research);
model time vs tool time vs idle gaps. Report the idle-gap distribution (p50, p90), never a
single cut; label gaps "review or absence", not "think time", and split them by whether the
turn before the gap ended in an edit or in a question. Session length,
compactions per session, crash/resume openers. Prompts typed in 3+ sessions.
Tool sequences of 3+ steps that recur and are not a skill yet: start from
`patterns.recurring_tool_sequences` (3-grams of argument-free tool tokens with the number of
sessions each appears in); for each sequence in 5+ sessions, read two sessions to name the
task it serves and say whether an installed skill already covers it (brief F has the list).
Interrupts and the action right before each: start from `patterns.interrupt_before_tool`
and `patterns.repeated_tool_calls` in the scan, then label each interrupt with one of: missing
context or correction, slow or excessive action, user takes the next step, requirement
change, other. `patterns.nudge_prompts` counts `proceed`/`continue` messages: 10+ in the
window means the user is driving a loop by hand; recommend `/goal <check>` with a runnable
check, or a Stop hook that runs a named command. Never recommend an "always continue" rule
or an unattended loop without a check: "keep going" is a retired practice and
over-persistence is a measured failure mode.

## C. Waits and operations
Top 20 Bash patterns by total wall time; calls over 120 s and 600 s timeouts;
identical retries (the `Bash` row of `patterns.repeated_tool_calls` is the count; find the
command prefixes; brief G interprets the other tools). `sleep`/`until`/`watch` loops and what they wait for (CI, deploy,
pod rollout, pipeline). Background runs: completed, failed, stopped, orphaned.
Remote commands (ssh, kubectl, docker, curl) split into read-only and write forms,
with the real command prefixes seen (rules must match those). Secret-reading forms
(`get secret`, `base64 -d`, `printenv`, `cat .env`, `-o yaml` on pods).

## D. Permissions and hooks
Classifier denials by reason and by command form; which are read-only (allow
candidates) and which must stay gated. Hook blocks by hook file and plugin, with the
hook's latency if measurable. Sizes of `permissions.allow` in every
`settings.local.json`; one-off absolute-path entries. Rules that would still prompt
under the proposed allow list (list the 10 most frequent unmatched prefixes).
`patterns.tool_wait_seconds_total_n_mean` gives result-minus-use time per non-Bash tool;
a mean over 3 s on Read, Grep, Glob or Edit is permission wait, not work: name the rule
that removes it. `patterns.dangerous_forms` lists `rm -rf`, `git push --force`, `git reset
--hard`, `git clean -f`, `--no-verify` counts: propose a deny rule or a PreToolUse hook for
each form seen more than 5 times, and say which population issued it. A hook block or a
classifier denial that landed on one of these forms is "prevented", not friction: report
them apart. Count the hooks in `settings.json` and in every enabled plugin; above 40, name
the ones that encode a preference rather than a guard. The 3 s wait mean and the 5-count
form threshold are heuristics, not validated limits; say so in the item.

## E. Subagent economics
Every `subagents/agent-*.jsonl` in the window, grouped by `agentType` from
`.meta.json`: runs, model, duration median/p90, fresh tokens median/p90, tool calls,
edits yes/no, failures/timeouts/TaskStop. Runs over 100k fresh tokens. Read-only
types running on the most expensive model. Parallelism: summed duration vs wall span;
same-file edits by concurrent agents. Rework: a later agent editing a file an earlier
agent wrote in the same session. Subagent fresh tokens over main-thread fresh tokens per
session: a share over 1 with wall span near the summed duration is sequential delegation
that bought no parallelism; flag Agent calls that edited one file with no concurrent sibling. `patterns.orphaned_agents` in the interactive population
counts Agent calls whose result never arrived before the session ended: each is a turn the
parent ended early (rule 7 of the skill). Do not use "parent edited after review" as a value
signal when the parent is an orchestrator.

## F. Config and instruction layer
Run `scripts/config_audit.sh` first. Then: plugin, skill, agent and MCP inventory
with usage counts from transcripts (name what disappears if each plugin is
disabled); duplicate skills (same name in `~/.claude/skills` and a plugin); hooks
per tool call and what text they inject; skill-description budget; CLAUDE.md
tokens per project; broken imports, dangling symlinks, empty files, files never
imported; contradictions between loaded files (quote both with path:line); grep
compliance of 10 checkable rules; user corrections that no rule records (session,
paraphrase, proposed rule, destination file); whether each project `CLAUDE.md` names the
command that runs its tests, typecheck and lint (a `file_append` item when it does not:
that line is the one with the strongest evidence behind it); emphasis and effort words in
instruction files and prompts (`IMPORTANT`, ALL CAPS, `ultrathink`, "think hard", "be
thorough", "don't be lazy"): count them, read `effort` on assistant records, and propose
`/effort` or the `effortLevel` setting instead; emphasis makes the model over-apply a rule.

Skill candidates from repeated prompts. The scan gives `repeated_prompts` (exact) and
`patterns.near_duplicate_prompts` (numbers, paths and quoted spans replaced); each entry is
`{hash, sessions, occurrences, files}` (`reference/schema.md`, "Prompt clusters"). For each
cluster, run
`python3 ${CLAUDE_SKILL_DIR}/scripts/prompt_samples.py --scan <scan.json> --hash <hash> --max 3`
(add `--near` for a near-duplicate hash, `--population headless` for that population). It
prints the samples and, per session, `commits=` and `interrupts=`: keep only samples from
sessions with a commit, a merged PR or an explicit user confirmation and no interrupt
right after the prompt. Never hash transcripts yourself and never paste a
`[redacted: secret-shaped]` sample anywhere. Then write the skill: the fixed steps as the
body, the parts that differed across samples as `$ARGUMENTS` or named placeholders, a
one-line `description`; the skill carries no literal path, branch, host, number or name from
any sample. A cluster with `sessions: 1` and high `occurrences` is one session's loop:
propose `/goal <check>` or a Stop hook, not a skill. State the benefit of a skill built from
a repeated prompt as typing and consistency, never as a better outcome: slash commands
measured no gain over plain prompting. A cluster whose sessions mostly failed becomes a
CLAUDE.md lesson ("when X, do not Y"), never a skill. Report cluster size (`sessions`,
`occurrences`), the proposed name and the destination path.

## G. Quality
Read-only `gh run list --limit 200`, `gh pr list --state all --limit 100`,
`git log --since`. CI failures on PR branches and their jobs; hotfixes;
PRs with 2+ fix commits and the cause of each fix (reviewer finding, CI, user,
self-correction, scope); which checks ran before "done" claims: the scan's `patterns.done_claims` and
`patterns.done_without_verify` count assistant text that claims tests pass or work is
complete with no test or lint command since the last user prompt; read 10 flagged turns
and report how many are real unverified claims (MAST FM-3.2, no or incomplete
verification) versus prose that mentions tests. `patterns.premature_sessions` counts
sessions whose first tool call edits before any read and `patterns.premature_corrected_sessions`
the subset the user corrected within 5 messages: report the second, the first is descriptive;
`patterns.churn_files_over_5_edits` counts files edited more than 5 times in one session;
`patterns.reverts` counts `git revert` and soft `git reset` and is never a quality headline
(revert rates of agent and human commits are alike). Loops: `patterns.repeated_tool_calls`
(identical input twice in a row, by tool), `patterns.search_loops_3plus` and
`patterns.failed_edit_streaks` (2+ failed Edit/Write results in a row; recovery odds fall with
each one), with `patterns.tool_error_rate` behind them: read 5 sessions per counter and name
what the loop waited for. `patterns.test_file_edits_in_fix_sessions` over `patterns.fix_sessions`:
a fix that edits the test file and then passes is how an agent clears an impossible task;
read every flagged session and say whether the test change was the fix or the cheat. For each, read 5 sessions and name the cause with one of: no runnable
check named, spec underspecified, edit before read, scope grew. Never "no plan mode" or "no
test first": neither is measured to help. State what the numbers cannot show.

## H. Security exposure
Literal tokens in `settings.json` `env`, `~/.claude.json` (`env`, `headers`), their
backups, `history.jsonl`, `file-history/`; transcripts containing `sk_live_`,
`rk_live_`, `Bearer `, decoded `kubectl get secret` output. Report key names, file
paths and counts only. Check the file `GOOGLE_APPLICATION_CREDENTIALS` points to
exists and its mode. Note how env vars reach GUI/cron launches (they do not read
`.zshrc`). No brief scans the code the agent wrote, where the measured security cost sits:
when the project has a scanner (semgrep, bandit, gitleaks, `npm audit`), propose a `manual`
item that runs it over the files agent sessions edited in the window.

## I. Context economics
Over all interactive sessions first: distributions (p50, p90) of compactions per session,
duplicate Reads and oversized results, from the scan. Then the 3 largest sessions as
examples, never as the measurement: compaction count, `preTokens` before each,
`postTokens` after, re-explaining in the next 5 user messages, duplicate Reads of the
same path and their cost, tool results over 20k chars by tool, and the first-request
size of a fresh session in the same project (the fixed overhead).

## K. Skill and tool coverage
Input: `inventory.json` (what is installed: `skills`, `mcp_servers`, `agents`) and the six
coverage keys at the end of each population summary in `scan.json`
(`skills_available`, `skills_used_distinct`, `missed_skill_sessions`,
`mcp_servers_configured`, `mcp_servers_used`, `mcp_servers_unused`). Interactive population
first; headless and subagent only when they invoke skills at all.

A `missed_skill_sessions` entry means: the skill was among the two best-matching installed,
model-invoked skills for a user prompt (3 trigger terms, plus one per 600 chars of prompt),
either in two distinct prompts of that session or in one prompt under 300 chars, and the
session never called it (thresholds in `reference/schema.md`). A keyword match is still a hint,
not a finding: a skill about "linkedin posts" matching a prompt that merely mentions LinkedIn
is a false positive. For each of the top skills read every listed location: a location is
`<hash>/<file>` plus a line; `python3 ${CLAUDE_SKILL_DIR}/scripts/scan_coverage.py --resolve <hash>`
prints the project dir, then `sed -n '<line>p' ~/.claude/projects/<project-dir>/<file>` (never
read the whole file). Decide whether invoking the skill would have changed
the result: a procedure the user then did by hand, a check the skill enforces that the session
skipped, a rule the user restated. Count real misses versus coincidences per skill and report
both numbers. One artefact to discard before reading: in the headless population, many
sessions flagging the same skill at the same line number are one automation prompt repeated
across sessions (schema population 4), one miss at most. The scanner already drops the third
and lower matches per prompt and single matches in long prompts, so a remaining shared location
is two skills that both fit; read it once and keep the one the task was about. Then produce items:

(a) a `review` item that extends the skill's `description` so it fires on the phrasing the user
    actually typed: `file_replace` on its `SKILL.md` (`path` in `inventory.json`), only for
    `source: user` or `source: project`. A plugin file is not editable: make a `manual` item
    "report upstream to <plugin>" or a `file_create` copy under `~/.claude/skills/<name>/` with
    the wider description, and name the duplicate it creates in `consumers`.
(b) a `review` `file_append` to the project `CLAUDE.md` naming the skill to use for that task
    family ("for keyword work, invoke `/keyword-research` before drafting").
(c) for each name in `mcp_servers_unused`: a `manual` item with `claude mcp remove <name>`
    (user or project-local scope; `~/.claude.json` is never edited by the apply skill) or
    the `.mcp.json` / plugin to disable for `project` and `plugin:` sources. State the cost as
    UNVERIFIED unless you measured the server's tool-definition tokens in a first request.
    A server whose name differs from its tool prefix (plugin servers are
    `plugin_<plugin>_<server>`) counts as used when any `mcp__<prefix>__*` call exists.
(d) skills installed but never invoked in the window are already brief F's inventory finding;
    do not duplicate them here. Report only skills that were matched and not invoked.

Items (a) and (b) are `review` with the benefit marked UNVERIFIED: generic skills matched
personalised ones in the one comparison. Keep each only after reading two sessions that show
a procedure the skill would have enforced and the session skipped. Item (c) stays as written.

Evidence per item: the skill name, `sessions` from `missed_skill_sessions`, the locations you
read, and the real-miss count. Never quote the prompt text.

## L. Prompting and the global instruction layer
Population `cli`, interactive sessions with 4+ real user messages. This angle reads how
the user writes, not how the harness is set up (A–K). Four parts.

1. Opening prompts. For 20 sessions drawn at random plus the 20 longest, read the first
   user message and grade it on four points: states the goal, names the done-criterion,
   names the files or paths, states a constraint (scope, model, budget). Then judge each of
   the next 5 user messages yourself as a correction or not (a message that negates or
   redirects the work); words such as `no`, `I meant`, `wrong` say where to read, not what
   to count. Report the correction share per grade (0 to 4 points met), the share of
   sessions corrected before the first commit, and which point the corrected prompts
   lacked most often.
2. Questions asked back. `AskUserQuestion` calls and the wait each caused
   (`tool_wait_seconds_total_n_mean`). For the 10 longest waits, read the question and the
   prompt before it: name what the prompt left open and the one line that would have
   pre-answered it (a `CLAUDE.md` default, a skill `$ARGUMENTS`, a rule such as "when X,
   assume Y"). A question the user answered the same way 3+ times is a missing rule. A
   question is a cost only when the prompt had already answered it; when the prompt was
   underspecified the question is the fix, and the item is the missing default, not the wait.
3. The global layer. `~/.claude/CLAUDE.md`, every file it imports, `~/.claude/rules/*.md`,
   and the text hooks inject on every prompt (`UserPromptSubmit`, `SessionStart`). Count
   its tokens. Quote every pair of overlapping or conflicting rules with `path:line` for
   both. For each rule that transcripts can check (file length, no scratch files, read
   before edit, tests before done), give the compliance count from the scan or a grep and
   say whether the rule, the wording or the placement should change. A rule that holds in
   100% of sessions is a candidate for removal only when it restates what the repo's
   linter, formatter or a hook already enforces, or describes architecture; one that fails
   in most sessions is a candidate for a hook, not a longer sentence.
4. Steering sentences. From `patterns.near_duplicate_prompts` and the correction turns of
   part 1, list the sentences the user types to steer (`proceed`, `use rtk`, `no notes`,
   `ask first`). Each becomes one of: a rule with its destination file, a
   `UserPromptSubmit` hook with `additionalContext` when it depends on the prompt, a
   user-invocable skill when it is a recurring task (hand the cluster to brief F's
   procedure), or nothing when it steered one session only. If the inventory says
   `insights_report=none`, propose a manual item that runs `/insights` and reads the report
   into the next audit.

Quote at most 15 words of any user prompt; never quote a sample marked
`[redacted: secret-shaped]`. Items from this angle go to phase 2 (instruction layer) or
phase 5 (workflow) with the session count behind each.

## J. Adversarial review (after the draft)
Give the full draft and ask: which disabled item is used (counts)? which rule misses
the real command form? which hook can loop or block on old errors or break in a
worktree? which copied agent references tools its plugin provided? does any step put
a secret in git, a prompt or a subprocess environment? which measurement is an
artefact? what breaks out of order; what is irreversible? For the pattern counters: is a
`git checkout -b` or `git checkout <branch>` counted as a revert (it must not be)? is
`--force-with-lease` counted as `--force` (it must not be)? does a "done" claim come from
a quoted rule or a plan rather than the assistant's own report? does a Read of
`.env.example` count as a credential read (it must not)? is a near-duplicate cluster the
same task or two tasks that share a sentence shape? does a proposed skill contain a path,
token or name from a sample prompt that must not be in a skill file? is a
`missed_skill_sessions` entry a keyword coincidence? read the location before keeping it. is
a hook block or classifier denial counted as friction when it prevented a `dangerous_forms`
command? is an `AskUserQuestion` counted as wait cost when the prompt before it was
underspecified? does every manual op carry `steps` with one action each and the exact command in
`code`, or a paragraph the user must parse? does each command in `code` match the
`--help` of the installed tool (flag order, variadic options such as `-e <env...>`)? does the
order of phase-0 items respect which value wins at runtime (settings `env` over shell)?
