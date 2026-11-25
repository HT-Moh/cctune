"""Sessions that ran at the same time in one project directory, counted from their time spans.

Two interactive sessions open on the same checkout at once share one working tree: one
session's edits land under the other's feet. `claude -w` gives each its own worktree; those
sessions live in a `--claude-worktrees-` project dir and are counted apart. Per session only
the hashed project dir, a worktree flag and the first and last event seconds are kept.
"""
import collections

from scan_paths import path_key

WORKTREE_MARK = "claude-worktrees"
MIN_OVERLAP_S = 60


class Concurrency:
    """Population state: session name to [project hash, worktree flag, first second, last second]."""

    def __init__(self):
        self.spans = {}


class SessionSpan:
    """Per-session memory."""

    def __init__(self, project_dir=""):
        self.group = path_key(project_dir)
        self.worktree = int(WORKTREE_MARK in project_dir)
        self.first = None
        self.last = None


def on_event(when, ss):
    if when is None:
        return
    ss.first = when if ss.first is None else min(ss.first, when)
    ss.last = when if ss.last is None else max(ss.last, when)


def finish_session(name, ss, c):
    if ss.first is not None:
        c.spans[name] = [ss.group, ss.worktree, ss.first, ss.last]


def _pairs(intervals):
    """Pairs of [first, last] intervals that overlap by more than MIN_OVERLAP_S, and the members."""
    ordered = sorted(intervals)
    pairs, members = 0, set()
    for i, (first, last, name) in enumerate(ordered):
        for other_first, other_last, other in ordered[i + 1:]:
            if other_first >= last - MIN_OVERLAP_S:
                break
            pairs += 1
            members.update((name, other))
    return pairs, members


def summary(c):
    by_group = collections.defaultdict(list)
    worktrees = 0
    for name, (group, worktree, first, last) in c.spans.items():
        if worktree:
            worktrees += 1
        else:
            by_group[group].append((first, last, name))
    pairs, members = 0, set()
    for intervals in by_group.values():
        group_pairs, group_members = _pairs(intervals)
        pairs += group_pairs
        members |= group_members
    return {"concurrent_session_pairs": pairs, "sessions_in_concurrent_pairs": len(members), "worktree_sessions": worktrees}
