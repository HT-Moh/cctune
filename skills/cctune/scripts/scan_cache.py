"""Per-transcript cache so a second audit reads only new or grown files.

A finished transcript never changes, so its contribution to a population is computed once and
stored as JSON under `~/.claude/tune/work/cache/`: counters, hashes and session names, the same
shape as `scan.json` and guarded by the same secret check. A record is reused when the file's
size and mtime, the scanner's source and the inventory are unchanged, and the window still
covers every event the record counted. `encode` and `merge_into` walk a `Pop` generically: a
Counter adds, a set unions, a list extends, a number sums, an object merges field by field.
"""
import collections
import glob
import hashlib
import json
import os
import re
import time

import scan_lib
from redact import has_secret

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "tune", "work", "cache")
DEFAULT_MAX_AGE_DAYS = 90
HEAD_BYTES = 400000
TIMESTAMP_RE = re.compile(r'"timestamp":\s*"([^"]{10,40})"')
# Per-session scratch and the inventory index live outside the record; `msg_ids` only dedupes within one file.
EXCLUDED_FIELDS = frozenset({"index", "msg_ids", "line"})


def scanner_version(script_dir, inventory_path):
    """Hash of every `scan*.py` plus the inventory file; any change invalidates every record."""
    digest = hashlib.sha256()
    for path in sorted(glob.glob(os.path.join(script_dir, "scan*.py"))):
        with open(path, "rb") as fh:
            digest.update(os.path.basename(path).encode("utf-8") + fh.read())
    if inventory_path:
        with open(inventory_path, "rb") as fh:
            digest.update(b"inventory" + fh.read())
    return digest.hexdigest()[:16]


def population_of(entrypoint, path):
    if "/subagents/" in path.replace(os.sep, "/"):
        return "subagent"
    return "interactive" if entrypoint in ("cli", "") else "headless"


def scan_one(path, index, max_bytes, cutoff):
    """Stream one transcript into a fresh `Pop`; returns (population, status, pop)."""
    pop = scan_lib.Pop(index)
    seen = []

    def pop_for(entrypoint, _path):
        seen.append(entrypoint)
        return pop

    status = scan_lib.scan_file(path, pop_for, max_bytes, cutoff)
    return population_of(seen[0] if seen else "", path), status, pop


def encode(value):
    """JSON-ready view of a `Pop` or any field of it."""
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(encode(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    return {k: encode(v) for k, v in vars(value).items() if not k.startswith("_") and k not in EXCLUDED_FIELDS}


def merge_into(target, data):
    """Add `data` (an encoded value) into `target`; returns the merged value for scalar fields."""
    if isinstance(target, collections.Counter):
        target.update(data)
    elif isinstance(target, dict):
        for key, value in data.items():
            target[key] = merge_into(target[key] if key in target else _fresh(target), value)
    elif isinstance(target, set):
        target.update(data)
    elif isinstance(target, list):
        target.extend(data)
    elif target is None:
        return data
    elif isinstance(target, (int, float)):
        return target + data
    else:
        for key, value in data.items():
            setattr(target, key, merge_into(getattr(target, key), value))
    return target


def _fresh(mapping):
    factory = getattr(mapping, "default_factory", None)
    return factory() if factory else None


def head_timestamp(path):
    """Timestamp of the first event; transcripts are append-only, so it is the earliest."""
    with open(path, "rb") as fh:
        head = fh.read(HEAD_BYTES).decode("utf-8", errors="replace")
    match = TIMESTAMP_RE.search(head)
    return scan_lib.ts(match.group(1)) if match else None


def record_for(path, population, status, pop, cutoff):
    first_ts = head_timestamp(path) if status == "ok" else None
    info = os.stat(path)
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns, "first_ts": first_ts,
            "complete": first_ts is not None and first_ts >= cutoff, "cutoff_day": _day(cutoff),
            "population": population, "status": status, "pop": encode(pop)}


def _day(cutoff):
    return int(cutoff // 86400)


class Cache:
    """Records keyed by the transcript path, valid for one scanner version."""

    def __init__(self, directory, version):
        self.directory = directory
        self.version = version
        self.hits = 0
        self.misses = 0
        self.refused = 0

    def _record_path(self, path):
        return os.path.join(self.directory, hashlib.sha256(os.path.realpath(path).encode("utf-8")).hexdigest()[:16] + ".json")

    def lookup(self, path, cutoff):
        """The stored record when the file, the scanner and the window still match, else None."""
        record = self._read(self._record_path(path))
        info = os.stat(path)
        if record is None or record.get("version") != self.version:
            return self._miss()
        if record["size"] != info.st_size or record["mtime_ns"] != info.st_mtime_ns:
            return self._miss()
        covers_window = record["complete"] and record["first_ts"] >= cutoff
        if not covers_window and record["cutoff_day"] != _day(cutoff):
            return self._miss()
        self.hits += 1
        return record

    def _miss(self):
        self.misses += 1
        return None

    @staticmethod
    def _read(record_path):
        try:
            with open(record_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def store(self, path, record):
        """Owner-only JSON; False (and nothing written) when the record looks like it holds a credential."""
        text = json.dumps({"version": self.version, **record})
        if has_secret(text):
            self.refused += 1
            return False
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        fd = os.open(self._record_path(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return True

    def prune(self, max_age_days=DEFAULT_MAX_AGE_DAYS):
        """Remove records not written for `max_age_days`; returns how many."""
        limit = time.time() - max_age_days * 86400
        removed = 0
        for name in os.listdir(self.directory) if os.path.isdir(self.directory) else []:
            record_path = os.path.join(self.directory, name)
            if name.endswith(".json") and os.path.getmtime(record_path) < limit:
                os.remove(record_path)
                removed += 1
        return removed
