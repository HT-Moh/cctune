# Report template

Write for a reader who acts on this in a month with no memory of the run. Name every
file. Numbers carry units and their source. No metaphors.

1. **Summary** (one paragraph): window, projects, sessions by population, the three
   biggest levers with numbers.
2. **Since the last audit**: the `metrics_delta.py` table as printed (id, population, key,
   before, after, change, since); one sentence per row whose change is zero or in the wrong
   direction. Omit the section only when the script prints that nothing was recorded.
3. **Findings by angle** (A–L): 3–8 bullets each, every bullet with count + path + method.
4. **Five biggest levers**: a five-row table (id, title, impact with its number) taken from
   `plan.json`; the full ranked list is on the page and in `<plan>.md`, never pasted into the
   terminal. Phases: 0 security (rotate, relocate, scrub) · 1 global config ·
   2 instruction files · 3 skills, rules and scripts · 4 pipelines · 5 habits · 6 later.
   Every id you mention exists in `plan.json`; never describe a change that has no item.
5. **Features from the docs the user does not use**, each with the use case taken
   from their own transcripts; plus skills installed but never matched or invoked, skills
   matched but not invoked (brief K, with the real-miss count after reading the locations),
   and MCP servers configured but never called.
6. **Suggested prompts, skills and rules**: a `SKILL.md` draft per repeated workflow
   (frontmatter, under 60 lines, inline `` !`cmd || true` `` for state); one-line
   rules for repeated corrections with the destination file; a `STATE.md` +
   `SessionStart` re-injection snippet if compactions are frequent.
7. **Automation candidates**: manual work a script, cron, or `claude -p` with
   `--max-turns` and `--output-format json` could do; cost per run; what stays manual.
8. **Contradiction check**: what the adversarial pass changed.
9. **Not verified**: each open item with the probe that would settle it.

End with the Artifact link of the rendered plan page and the line
`Pick items on the page, or run /cctune-apply --dry-run safe`.
