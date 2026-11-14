"""Load, validate and lock plan files under ~/.claude/tune/plans/; state goes to the ledger.

A plan file is an immutable proposal. `load_plan` picks the newest one (by `generated`) when
no path is given, migrates and validates it, then overlays the ledger's state onto its items.
`save_plan` appends the changed statuses to the ledger and never rewrites the plan file;
`rewrite_plan` does, and only `--migrate` calls it. A plan outside the plans directory is
refused. One lock guards every load-modify-save.
"""
import contextlib
import fcntl
import glob
import json
import os
import re
from pathlib import Path

import ledger
from plan_migrate import migrate_v1
from plan_schema import PlanError, validate

FILE_MODE = 0o600
GENERATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
DIR_MODE = 0o700


def plans_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "tune" / "plans"


def lock_path() -> Path:
    return plans_dir().parent / ".lock"


def _inside_plans_dir(path: Path) -> Path:
    real = Path(os.path.realpath(path))
    if real.parent != plans_dir().resolve():
        raise PlanError(f"{path} is not inside {plans_dir()}; plans live there only")
    return real


def _generated(path: str) -> str:
    """The plan's ISO `generated` stamp, or '' when missing or not a date (so garbage never wins)."""
    try:
        with open(path, encoding="utf-8") as fh:
            stamp = str(json.load(fh).get("generated", ""))
    except (OSError, ValueError, AttributeError):
        return ""
    return stamp if GENERATED_RE.match(stamp) else ""


def newest_plan() -> Path | None:
    """The real plan file with the latest `generated`, ties broken by name; None when there is none."""
    files = [p for p in glob.glob(str(plans_dir() / "*.json")) if not os.path.islink(p)]
    if not files:
        return None
    return Path(max(files, key=lambda p: (_generated(p), p)))


def load_plan(path: str | None) -> tuple[dict, Path]:
    """The plan (migrated, validated, with ledger state overlaid) and the file it came from."""
    ledger.bootstrap()
    chosen = Path(path) if path else newest_plan()
    if chosen is None or not chosen.exists():
        raise PlanError(f"no plan at {chosen or plans_dir()}. Run /cctune first.")
    real = _inside_plans_dir(chosen)
    with open(real, encoding="utf-8") as fh:
        plan = migrate_v1(json.load(fh))
    errors = validate(plan)
    if errors:
        raise PlanError("invalid plan:\n" + "\n".join("  " + e for e in errors))
    ledger.overlay(plan)
    return plan, real


def save_plan(plan: dict, path: Path) -> None:
    """Record every changed item state and the page URL in the ledger; the plan file stays as written."""
    real = _inside_plans_dir(path)
    ledger.record(plan["items"], ledger.load_state(), run=real.name)
    url = plan.get("page_url")
    if url and url != ledger.page_url():
        ledger.set_page_url(url)


def rewrite_plan(plan: dict, path: Path) -> None:
    """Write the plan file itself atomically, owner-only (schema migration only)."""
    real = _inside_plans_dir(path)
    tmp = real.with_name(f".{real.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=1, ensure_ascii=False)
        os.chmod(tmp, FILE_MODE)
        os.replace(tmp, real)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


@contextlib.contextmanager
def locked():
    """Hold ~/.claude/tune/.lock for the duration; a second holder blocks until release."""
    lock = lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, FILE_MODE)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
