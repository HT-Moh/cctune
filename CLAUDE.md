# cctune

Two Claude Code skills: `skills/cctune` (read-only audit) and `skills/cctune-apply` (the only
writer). Python standard library only.

## Check before done

```bash
python3 -m pytest -q
ruff check skills tests
```

CI runs both on Python 3.10 and 3.12. Files under 300 lines, functions under 30, one concern
per commit, a failing test before each fix. Nothing prints or stores a secret value.
