"""A fingerprint names the change an item makes, not the item.

Two audit runs that propose the same write get the same fingerprint whatever id, title or
wording they use, so the ledger can carry status from one plan to the next. JSON ops key on
kind, file and path (not the value: the same setting proposed with a new value is the same
change evolving). Text ops key on normalised text. Manual ops key on their step commands,
falling back to the summary text. Home is written as `~` so one machine's ledger describes
the same change on another.
"""
import hashlib
import json
import os
import re

JSON_OPS = ("json_set", "json_delete", "json_append", "json_upsert")
TEXT_OPS = {"file_create": "content", "file_append": "content", "file_replace": "new"}
PUNCT_RE = re.compile(r"[^\w\s]")
DIGEST_CHARS = 16


def normal_file(path: str) -> str:
    expanded = os.path.expanduser(str(path))
    home = os.path.expanduser("~")
    if expanded == home or expanded.startswith(home + os.sep):
        return "~" + expanded[len(home):]
    return expanded


def normal_text(text) -> str:
    return " ".join(PUNCT_RE.sub(" ", str(text or "").lower()).split())


def op_key(op: dict) -> list:
    kind = op.get("kind")
    if kind in JSON_OPS:
        return [kind, normal_file(op.get("file", "")), [str(p) for p in op.get("path") or []]]
    if kind in TEXT_OPS:
        return [kind, normal_file(op.get("file", "")), normal_text(op.get(TEXT_OPS[kind]))]
    if kind == "file_remove":
        return [kind, normal_file(op.get("file", ""))]
    if kind == "symlink":
        return [kind, normal_file(op.get("link", "")), str(op.get("target", ""))]
    if kind == "manual":
        codes = [normal_text(s.get("code")) for s in op.get("steps") or [] if s.get("code")]
        return [kind, codes or normal_text(op.get("text"))]
    return [str(kind)]


def fingerprint(item: dict) -> str:
    basis = [op_key(op) for op in item.get("ops") or [] if isinstance(op, dict)]
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode("utf-8")).hexdigest()[:DIGEST_CHARS]
