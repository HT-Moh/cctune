"""The one place item state lives: `~/.claude/tune/ledger.jsonl`, append-only, keyed by fingerprint.

Plan files are immutable proposals. Every status change (applied, done, rolled back, failed,
dismissed) is one appended event carrying the item's state snapshot; the last event per
fingerprint wins. `overlay` writes that state onto whatever plan is being read, so a new audit
run shows items applied under an earlier plan as applied. The page URL is an event too. An
unreadable line is skipped with a warning, never fatal. Callers hold `plan_store.locked()`.
"""
import datetime as dt
import glob
import json
import os
from pathlib import Path

from plan_fingerprint import fingerprint

STATE_FIELDS = ("status", "error", "reason", "applied_at", "done_at", "files", "backup")
FILE_MODE = 0o600
DIR_MODE = 0o700
_warnings: list = []


def ledger_path() -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "tune" / "ledger.jsonl"


def warnings() -> list:
    return list(_warnings)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _events() -> list:
    _warnings.clear()
    path = ledger_path()
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for n, raw in enumerate(fh, 1):
            try:
                ev = json.loads(raw)
            except ValueError:
                ev = None
            if isinstance(ev, dict):
                out.append(ev)
            elif raw.strip():
                _warnings.append(f"ledger line {n} unreadable, skipped")
    return out


def _last_by_fp() -> dict:
    last = {}
    for ev in _events():
        if "fp" in ev:
            last[ev["fp"]] = ev
    return last


def load_state() -> dict:
    """fingerprint -> state fields of its last event."""
    return {key: {k: ev[k] for k in STATE_FIELDS if k in ev} for key, ev in _last_by_fp().items()}


def page_url():
    url = None
    for ev in _events():
        url = ev.get("page_url", url)
    return url


def snapshot(item: dict) -> dict:
    out = {"status": item.get("status", "proposed")}
    out.update({k: item[k] for k in STATE_FIELDS[1:] if k in item})
    return out


def _append(events: list) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, FILE_MODE)
    try:
        os.write(fd, "".join(json.dumps(ev, ensure_ascii=False) + "\n" for ev in events).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def record(items: list, before: dict, run: str) -> int:
    """Append one event per item whose state differs from `before` (fingerprint -> state); return the count."""
    events = []
    for it in items:
        key = fingerprint(it)
        snap = snapshot(it)
        if before.get(key, {"status": "proposed"}) != snap:
            events.append({"t": _now(), "fp": key, "id": it.get("id"), "title": it.get("title", ""), "run": run, **snap})
    if events:
        _append(events)
    return len(events)


def set_page_url(url: str) -> None:
    _append([{"t": _now(), "page_url": url}])


def overlay(plan: dict) -> dict:
    """Write ledger state onto the plan's items (by fingerprint) and its page URL; return the state used."""
    state = load_state()
    for it in plan.get("items") or []:
        known = state.get(fingerprint(it))
        if known is None:
            continue
        for k in STATE_FIELDS:
            it.pop(k, None)
        it.update(known)
    url = page_url()
    if url:
        plan["page_url"] = url
    return state


def history() -> list:
    rows = [{"fp": key, "id": ev.get("id"), "run": ev.get("run"), "status": ev.get("status"), "title": ev.get("title", "")}
            for key, ev in _last_by_fp().items()]
    return sorted(rows, key=lambda r: (str(r["run"]), str(r["id"])))


def _legacy_plans() -> list:
    """(generated, name, plan) for every real plan file, oldest first."""
    rows = []
    for path in glob.glob(str(ledger_path().parent / "plans" / "*.json")):
        if os.path.islink(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                plan = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(plan, dict):
            rows.append((str(plan.get("generated", "")), os.path.basename(path), plan))
    return sorted(rows)


def bootstrap() -> int:
    """Once, when no ledger exists: import every non-proposed status from the plan files; drop latest.json."""
    if ledger_path().exists():
        return 0
    imported = 0
    _append([])
    for _generated, name, plan in _legacy_plans():
        items = [it for it in plan.get("items") or [] if isinstance(it, dict) and it.get("status", "proposed") != "proposed"]
        imported += record(items, {}, run=name)
        if plan.get("page_url"):
            set_page_url(plan["page_url"])
    latest = ledger_path().parent / "plans" / "latest.json"
    if latest.is_symlink():
        latest.unlink()
    return imported
