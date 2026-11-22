"""Bounded privacy-safe latency aggregation across Jade transports.

Metric names are explicit about the observation point: network delivery is
never presented as proof that the end user heard the first audio sample.
"""
from __future__ import annotations

from collections import defaultdict, deque
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

    def end(self, turn, outcome="complete"):
        current = self.pending.pop(turn, None)
        if current is None:
            return
        row = dict(current["stages"])
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
                             if k not in ("outcome",)})
            for stage in stages:
                values = [record[stage] for record in data
                          if isinstance(record.get(stage), (int, float))
                          and math.isfinite(record[stage])]
                points[stage] = {"n": len(values), "p50_ms": _percentile(values, 0.5),
                                 "p95_ms": _percentile(values, 0.95)}
            result.append({"platform": platform, "modality": modality,
                           "samples": len(data), "latency": points,
                           "failed": sum(x["outcome"] != "complete" for x in data),
                           "first_audible_ms": None,  # client-side evidence required
                           "cost_usd": None})  # not inferred from delayed billing
        return result
