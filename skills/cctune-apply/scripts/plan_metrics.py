"""The optional `metrics` field of a plan item: which scan values justified it.

`{"population": "interactive", "keys": {"patterns.nudge_prompts": 72}}` names the population
summary in `scan.json` and the numeric keys the audit read. The ledger keeps these values with
the event that records the item as applied or done; `metrics_delta.py` in the audit skill pairs
them with the next scan so the report can say whether the number moved.
"""
POPULATIONS = ("interactive", "headless", "subagent")


def validate_metrics(it: dict, tag: str) -> list[str]:
    """Optional `metrics`: the population and the numeric scan keys that justified the item."""
    metrics = it.get("metrics")
    if metrics is None:
        return []
    if not isinstance(metrics, dict):
        return [f"{tag}: metrics must be an object with population and keys"]
    errs = []
    if metrics.get("population") not in POPULATIONS:
        errs.append(f"{tag}: metrics.population must be one of {POPULATIONS}")
    keys = metrics.get("keys")
    if not isinstance(keys, dict) or not keys or any(
            not isinstance(v, (int, float)) or isinstance(v, bool) for v in keys.values()):
        errs.append(f"{tag}: metrics.keys must map scan keys to numbers")
    return errs
