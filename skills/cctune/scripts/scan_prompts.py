"""Prompt clustering without content: a normalised hash per message, counts per session.

`near_key` groups prompts that differ only in numbers, paths and quoted spans; `is_nudge`
spots whole-message `proceed`/`continue` prompts. `PromptCluster` and `cluster_rows` are
shared with the exact-prompt clusters in `scan_lib`.
"""
import hashlib
import re

NUDGES = frozenset({"proceed", "continue", "yes", "y", "ok", "okay", "go", "go on", "go ahead", "next", "do it",
                    "continue please", "proceed please", "yes proceed", "ok proceed"})
NEAR_NUMBER_RE = re.compile(r"\d+")
NEAR_PATH_RE = re.compile(r"\S*/\S*")
NEAR_QUOTE_RE = re.compile(r"(\"[^\"]*\"|'[^']*'|`[^`]*`)")
NEAR_PUNCT_RE = re.compile(r"[^\w\s<>]")



def near_key(text):
    """Hash of the prompt with numbers, paths and quoted spans replaced; groups near-duplicates."""
    s = NEAR_QUOTE_RE.sub("<q>", text.lower())
    s = NEAR_PATH_RE.sub("<path>", s)
    s = NEAR_NUMBER_RE.sub("0", s)
    s = " ".join(NEAR_PUNCT_RE.sub(" ", s).split())
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def is_nudge(text):
    return " ".join(NEAR_PUNCT_RE.sub(" ", text.lower()).split()) in NUDGES



CLUSTER_MIN_SESSIONS = 3
CLUSTER_MIN_OCCURRENCES = 5
CLUSTER_FILES_KEPT = 5
CLUSTER_ROWS_KEPT = 15


class PromptCluster:
    """Every message that hashes to one key: how many, in how many sessions, and where to look."""

    def __init__(self):
        self.sessions = set()
        self.occurrences = 0
        self.files = []

    def add(self, session_name):
        self.occurrences += 1
        if session_name not in self.sessions and len(self.files) < CLUSTER_FILES_KEPT:
            self.files.append(session_name)
        self.sessions.add(session_name)

    def is_recurring(self):
        return len(self.sessions) >= CLUSTER_MIN_SESSIONS or self.occurrences >= CLUSTER_MIN_OCCURRENCES


def cluster_rows(clusters):
    """JSON-ready rows for the recurring clusters, most occurrences first, top 15."""
    kept = sorted(((c.occurrences, k) for k, c in clusters.items() if c.is_recurring()), reverse=True)
    return [{"hash": k, "sessions": len(clusters[k].sessions), "occurrences": n, "files": list(clusters[k].files)}
            for n, k in kept[:CLUSTER_ROWS_KEPT]]
