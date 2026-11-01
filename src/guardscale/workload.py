"""Deterministic synthetic workloads with explicit labels and behavior signals."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Window:
    second: int
    legitimate_rps: float
    attack_rps: float
    source_diversity: float
    regularity: float

    @property
    def offered_rps(self) -> float:
        return self.legitimate_rps + self.attack_rps

    @property
    def attack_fraction(self) -> float:
        return self.attack_rps / self.offered_rps if self.offered_rps else 0.0

    @property
    def risk_score(self) -> float:
        # Transparent toy heuristic: low source diversity and high timing
        # regularity look suspicious. This is deliberately not ML or a claim
        # about real attack detection quality.
        return min(1.0, max(0.0, 0.55 * (1 - self.source_diversity) + 0.45 * self.regularity))


SCENARIOS = ("legitimate_flash", "attack_flood", "adaptive_attack", "legitimate_lookalike")


def make_scenario(name: str, seed: int = 1, duration: int = 420) -> list[Window]:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; choose from {', '.join(SCENARIOS)}")
    if duration < 180:
        raise ValueError("duration must be at least 180 seconds")

    rng = random.Random(seed)
    rows: list[Window] = []
    for second in range(duration):
        # Quiet baseline, then a sharp 180-second arrival event, then recovery.
        baseline = 18.0
        if 90 <= second < 270:
            phase = (second - 90) / 180
            shape = min(1.0, phase * 8, (1 - phase) * 8)
            total = baseline + 220 * max(0.15, shape)
        else:
            total = baseline
        total *= rng.uniform(0.94, 1.06)

        if name == "legitimate_flash":
            legitimate, attack = total, 0.0
            diversity, regularity = rng.gauss(0.92, 0.025), rng.gauss(0.22, 0.04)
        elif name == "attack_flood":
            legitimate, attack = baseline * 0.25, max(0.0, total - baseline * 0.25)
            diversity, regularity = rng.gauss(0.12, 0.025), rng.gauss(0.88, 0.04)
        elif name == "adaptive_attack":
            legitimate, attack = baseline * 0.25, max(0.0, total - baseline * 0.25)
            # The attack imitates the simple diversity/timing signals.
            diversity, regularity = rng.gauss(0.84, 0.035), rng.gauss(0.27, 0.05)
        else:
            legitimate, attack = total, 0.0
            # Legitimate, low-diversity automated release/event resembles the
            # adaptive attack on purpose, exposing false-positive behavior.
            diversity, regularity = rng.gauss(0.84, 0.035), rng.gauss(0.27, 0.05)

        rows.append(Window(
            second=second,
            legitimate_rps=max(0.0, legitimate),
            attack_rps=max(0.0, attack),
            source_diversity=min(1.0, max(0.0, diversity)),
            regularity=min(1.0, max(0.0, regularity)),
        ))
    return rows


def write_csv(path: str | Path, rows: list[Window]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("second", "legitimate_rps", "attack_rps", "source_diversity", "regularity"))
        for row in rows:
            writer.writerow((row.second, f"{row.legitimate_rps:.4f}", f"{row.attack_rps:.4f}",
                             f"{row.source_diversity:.4f}", f"{row.regularity:.4f}"))


def read_csv(path: str | Path) -> list[Window]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"second", "legitimate_rps", "attack_rps", "source_diversity", "regularity"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"trace must include columns: {', '.join(sorted(required))}")
        return [Window(int(row["second"]), float(row["legitimate_rps"]), float(row["attack_rps"]),
                       float(row["source_diversity"]), float(row["regularity"])) for row in reader]


def estimate_forecast(history: list[float], horizon: int = 20) -> float:
    """Causal trend forecast from two adjacent 10-second means."""
    if not history:
        return 0.0
    recent = history[-10:]
    recent_mean = sum(recent) / len(recent)
    prior = history[-20:-10]
    if not prior:
        return recent_mean
    prior_mean = sum(prior) / len(prior)
    per_second_slope = (recent_mean - prior_mean) / 10
    # Clip trend extrapolation to avoid an unbounded linear controller.
    return max(0.0, recent_mean + max(-5.0, min(5.0, per_second_slope)) * horizon)
