"""A transparent discrete-time queue and replica-startup simulator."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .policy import ScalingObservation, decide
from .workload import Window, estimate_forecast


@dataclass(frozen=True)
class SimulationConfig:
    rps_per_replica: float = 60.0
    startup_seconds: int = 20
    min_replicas: int = 1
    max_replicas: int = 12
    max_predictive_step: int = 4
    slo_latency_seconds: float = 2.0
    forecast_horizon_seconds: int = 20
    downscale_stabilization_seconds: int = 30
    downscale_interval_seconds: int = 10


def _pick_target(policy: str, current: int, observed: float, forecast: float,
                 risk: float, config: SimulationConfig) -> tuple[int, str]:
    cap = config.rps_per_replica
    reactive = min(config.max_replicas, max(config.min_replicas, math.ceil(observed / cap)))
    predictive = min(config.max_replicas, max(config.min_replicas, math.ceil(forecast / cap)))
    if policy == "reactive":
        return reactive, "reactive"
    if policy == "predictive":
        return predictive, "forecast"
    if policy == "fixed_gate":
        return (reactive, "fixed_risk_gate") if risk >= 0.6 else (predictive, "forecast")
    if policy == "guardscale":
        # The policy primitive intentionally handles scale-up only; the
        # simulated HPA/downscale controller may reduce replicas once both
        # observed and predicted demand fit below current capacity.
        if max(reactive, predictive) < current:
            return max(config.min_replicas, reactive, predictive), "stabilized_scale_down_candidate"
        result = decide(ScalingObservation(
            current_replicas=current,
            min_replicas=config.min_replicas,
            max_replicas=config.max_replicas,
            observed_rps=observed,
            forecast_rps=forecast,
            rps_per_replica=cap,
            attack_risk_upper=min(1.0, risk + 0.05),
            max_predictive_step=config.max_predictive_step,
        ))
        return result.desired_replicas, result.reason
    raise ValueError(f"unknown policy: {policy}")


def _weighted_percentile(weighted: list[tuple[float, float]], percentile: float) -> float:
    if not weighted:
        return 0.0
    weighted.sort(key=lambda pair: pair[0])
    total = sum(weight for _, weight in weighted)
    threshold = total * percentile
    cumulative = 0.0
    for value, weight in weighted:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return weighted[-1][0]


def simulate(policy: str, scenario: str, seed: int, rows: list[Window],
             config: SimulationConfig | None = None) -> dict:
    config = config or SimulationConfig()
    if not rows:
        raise ValueError("cannot simulate an empty trace")

    desired = config.min_replicas
    ready_at = [0 for _ in range(desired)]
    backlog = 0.0
    history: list[float] = []
    weighted_latency: list[tuple[float, float]] = []
    total_legitimate = 0.0
    violating_legitimate = 0.0
    replica_seconds = 0.0
    max_ready = 0
    scale_actions = 0
    downscale_candidate_since: int | None = None
    last_downscale_at = -config.downscale_interval_seconds
    decision_log: list[dict] = []
    desired_trajectory: list[int] = []

    for row in rows:
        observed = row.offered_rps
        forecast = estimate_forecast(history, config.forecast_horizon_seconds)
        target, reason = _pick_target(policy, desired, observed, forecast, row.risk_score, config)
        target = min(config.max_replicas, max(config.min_replicas, target))
        if target < desired:
            if downscale_candidate_since is None:
                downscale_candidate_since = row.second
            ready_to_downscale = row.second - downscale_candidate_since >= config.downscale_stabilization_seconds
            interval_elapsed = row.second - last_downscale_at >= config.downscale_interval_seconds
            if ready_to_downscale and interval_elapsed:
                target = max(target, desired - 1)
                last_downscale_at = row.second
            else:
                target = desired
        else:
            downscale_candidate_since = None
        if target != desired:
            scale_actions += 1
            decision_log.append({"second": row.second, "from": desired, "to": target,
                                 "reason": reason, "risk": round(row.risk_score, 3),
                                 "forecast_rps": round(forecast, 2)})
        if target > desired:
            ready_at.extend([row.second + config.startup_seconds] * (target - desired))
        elif target < desired:
            # Remove unready pods first, then ready pods. This approximates
            # immediate termination; startup latency remains explicit.
            ready_at.sort()
            ready_at = ready_at[:target]
        desired = target
        desired_trajectory.append(desired)

        ready = sum(ready_second <= row.second for ready_second in ready_at)
        max_ready = max(max_ready, ready)
        capacity = ready * config.rps_per_replica
        incoming = observed
        backlog = max(0.0, backlog + incoming - capacity)
        latency = 1.0 + backlog / max(capacity, config.rps_per_replica)
        total_legitimate += row.legitimate_rps
        if latency > config.slo_latency_seconds:
            violating_legitimate += row.legitimate_rps
        if row.legitimate_rps:
            weighted_latency.append((latency, row.legitimate_rps))
        replica_seconds += desired
        history.append(observed)

    attack_seconds = sum(row.attack_rps > 0 for row in rows)
    duration = len(rows)
    return {
        "scenario": scenario,
        "policy": policy,
        "seed": seed,
        "duration_seconds": duration,
        "replica_seconds": round(replica_seconds, 2),
        "mean_desired_replicas": round(replica_seconds / duration, 3),
        "max_ready_replicas": max_ready,
        "scale_actions": scale_actions,
        "legitimate_requests_slo_violation_pct": round(
            100 * violating_legitimate / total_legitimate if total_legitimate else 0.0, 3
        ),
        "legitimate_request_p95_latency_estimate_seconds": round(_weighted_percentile(weighted_latency, 0.95), 3),
        "attack_window_replica_seconds": round(
            sum(desired for desired, row in zip(desired_trajectory, rows) if row.attack_rps > 0), 2
        ) if attack_seconds else 0.0,
        "evidence_type": "synthetic_simulation",
        "assumptions": asdict(config),
        "decisions": decision_log,
}
