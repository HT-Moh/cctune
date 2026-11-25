"""Files read or edited outside the session's working directory, counted without keeping a path.

A session that reaches into a second repository works without that repository's instructions
and permissions; `additionalDirectories` in settings or `--add-dir` gives it both. The working
directory comes from the `cwd` field on user and assistant events. Paths under the scratchpad
(`/tmp`) and under `~/.claude` are the agent's own and do not count; relative paths resolve
inside the working directory and do not count either. Only hashed directories are kept.
"""
import hashlib
import os

PATH_TOOLS = {"Read": "file_path", "Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "Grep": "path", "Glob": "path"}
OWN_PREFIXES = ("/tmp/",)
OWN_DIR_NAMES = (".claude",)


def path_key(path):
    """12 hex chars standing for a path; every path the scan stores goes through it."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]


class Paths:
    """Population counters."""

    def __init__(self):
        self.calls_outside = 0
        self.sessions_outside = 0
        self.outside_dirs = set()


class SessionPaths:
    """Per-session memory: the working directory and the outside directories touched."""

    def __init__(self):
        self.cwd = None
        self.outside_dirs = set()


def on_event(ev, sp):
    cwd = ev.get("cwd")
    if isinstance(cwd, str) and cwd.startswith("/"):
        sp.cwd = cwd.rstrip("/") or "/"


def is_outside(path, cwd):
    """True for an absolute path that is neither under `cwd` nor one of the agent's own places."""
    if not cwd or not isinstance(path, str) or not path.startswith("/"):
        return False
    normalized = os.path.normpath(path)
    if normalized == cwd or normalized.startswith(cwd + "/"):
        return False
    if normalized.startswith(OWN_PREFIXES):
        return False
    return not any(f"/{name}/" in normalized + "/" for name in OWN_DIR_NAMES)


def on_tool_use(name, inp, sp, p):
    field = PATH_TOOLS.get(name)
    if field is None:
        return
    path = inp.get(field, "")
    if is_outside(path, sp.cwd):
        p.calls_outside += 1
        sp.outside_dirs.add(path_key(os.path.dirname(os.path.normpath(path))))


def finish_session(sp, p):
    if sp.outside_dirs:
        p.sessions_outside += 1
        p.outside_dirs |= sp.outside_dirs


def summary(p):
    return {"calls_outside_cwd": p.calls_outside, "sessions_outside_cwd": p.sessions_outside,
            "outside_dirs_distinct": len(p.outside_dirs)}
