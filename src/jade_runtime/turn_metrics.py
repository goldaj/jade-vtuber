"""Bounded privacy-safe latency aggregation across Jade transports.

Metric names are explicit about the observation point: network delivery is
never presented as proof that the end user heard the first audio sample.
"""
from __future__ import annotations

from collections import defaultdict, deque
from contextvars import ContextVar
import math
import time


def _percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    left = int(pos)
    right = min(len(ordered) - 1, left + 1)
    return round(ordered[left] + (ordered[right] - ordered[left]) * (pos - left), 1)

# Local to the active async request, never a global model/provider cost counter.
_ACTIVE = ContextVar("jade_active_metrics", default=None)


def bind_metrics(metrics, turn):
    return _ACTIVE.set((metrics, turn))


def reset_metrics(token):
    _ACTIVE.reset(token)


def record_model_usage(input_tokens, output_tokens):
    active = _ACTIVE.get()
    if active is None:
        return
    if (type(input_tokens) is not int or input_tokens < 0
            or type(output_tokens) is not int or output_tokens < 0):
        return  # Missing usage cannot be estimated from the text length.
    metrics, turn = active
    metrics.add_tokens(turn, input_tokens=input_tokens, output_tokens=output_tokens)


class TurnMetrics:
    def __init__(self, *, max_samples=128, clock=time.monotonic):
        self.max_samples = max_samples
        self.clock = clock
        self.pending = {}
        self.samples = defaultdict(lambda: deque(maxlen=self.max_samples))

    def begin(self, turn, platform, modality, queued_at):
        self.pending[turn] = {
            "key": (platform, modality),
            "queued_at": queued_at,
            "stages": {},
        }

    def mark(self, turn, stage):
        current = self.pending.get(turn)
        if current is None:
            return
        # Do not store contents, identities, participant names or channel IDs.
        current["stages"].setdefault(stage, round(
            (self.clock() - current["queued_at"]) * 1000, 1))

    def add_tokens(self, turn, *, input_tokens, output_tokens):
        current = self.pending.get(turn)
        if current is None:
            return
        current["input_tokens"] = current.get("input_tokens", 0) + input_tokens
        current["output_tokens"] = current.get("output_tokens", 0) + output_tokens

    def end(self, turn, outcome="complete"):
        current = self.pending.pop(turn, None)
        if current is None:
            return
        row = dict(current["stages"])
        if "input_tokens" in current:
            row["input_tokens"] = current["input_tokens"]
            row["output_tokens"] = current["output_tokens"]
        if outcome == "complete":
            if "turn_failed" in row:
                outcome = "failed"
            elif "turn_cancelled" in row:
                outcome = "cancelled"
        row["total_ms"] = round((self.clock() - current["queued_at"]) * 1000, 1)
        row["outcome"] = outcome
        self.samples[current["key"]].append(row)

    def summary(self):
        result = []
        for (platform, modality), samples in sorted(self.samples.items()):
            data = list(samples)
            points = {}
            stages = sorted({k for record in data for k in record
                             if k not in ("outcome", "input_tokens", "output_tokens")})
            for stage in stages:
                values = [record[stage] for record in data
                          if isinstance(record.get(stage), (int, float))
                          and math.isfinite(record[stage])]
                points[stage] = {"n": len(values), "p50_ms": _percentile(values, 0.5),
                                 "p95_ms": _percentile(values, 0.95)}
            result.append({"platform": platform, "modality": modality,
                           "samples": len(data), "latency": points,
                           "failed": sum(x["outcome"] != "complete" for x in data),
                           "usage": {
                               "n": sum("input_tokens" in item for item in data),
                               "input_tokens": sum(item.get("input_tokens", 0) for item in data),
                               "output_tokens": sum(item.get("output_tokens", 0) for item in data),
                           },
                           "first_audible_ms": None,  # device/OS cannot confirm ears
                           "cost_usd": None})  # no unverified unit-price estimate
        return result
