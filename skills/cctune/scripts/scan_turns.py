"""Turn shape and context size per session, counted while streaming.

Human turns and tool calls per turn (Anthropic's internal baseline moved from 6.2 to 4.1
turns and 9.8 to 21.2 calls), an edit after a short prompt with no question asked back that
the user then corrected (underspecified task, the strongest measured productivity lever),
and assistant turns whose context exceeds 200k tokens (where effective recall degrades).
"""
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHORT_PROMPT_CHARS = 300
CONTEXT_CAP_TOKENS = 200000


class Turns:
    """Population counters."""

    def __init__(self):
        self.human_turns = []
        self.human_turns_total = 0
        self.tool_calls_total = 0
        self.short_prompt_edits = 0
        self.turns_above_cap = 0
        self.edits_above_cap = 0


class SessionTurns:
    """Per-session memory."""

    def __init__(self):
        self.human_turns = 0
        self.tool_calls = 0
        self.first_prompt_short = None
        self.asked = False
        self.first_edit_done = False
        self.unasked_short_edit = False
        self.last_ctx = 0


def on_prompt(text, st):
    st.human_turns += 1
    if st.first_prompt_short is None:
        st.first_prompt_short = len(text) < SHORT_PROMPT_CHARS


def on_assistant_text(text, st):
    if "?" in text and not st.first_edit_done:
        st.asked = True


def on_usage(usage, st, t):
    st.last_ctx = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    if st.last_ctx > CONTEXT_CAP_TOKENS:
        t.turns_above_cap += 1


def on_tool_use(name, st, t):
    st.tool_calls += 1
    if name == "AskUserQuestion" and not st.first_edit_done:
        st.asked = True
    if name not in EDIT_TOOLS:
        return
    if st.last_ctx > CONTEXT_CAP_TOKENS:
        t.edits_above_cap += 1
    if not st.first_edit_done:
        st.first_edit_done = True
        st.unasked_short_edit = bool(st.first_prompt_short) and not st.asked


def finish_session(st, corrected, t):
    t.human_turns.append(st.human_turns)
    t.human_turns_total += st.human_turns
    t.tool_calls_total += st.tool_calls
    t.short_prompt_edits += int(st.unasked_short_edit and corrected)


def _pct(values, q):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def summary(t):
    per_turn = round(t.tool_calls_total / t.human_turns_total, 1) if t.human_turns_total else None
    return {"human_turns_per_session_median": _pct(t.human_turns, 0.5), "human_turns_per_session_p90": _pct(t.human_turns, 0.9),
            "tool_calls_per_human_turn": per_turn, "edit_without_question_short_prompt": t.short_prompt_edits,
            "turns_above_200k": t.turns_above_cap, "edits_above_200k": t.edits_above_cap}
