"""Small, deterministic policy primitive used by the offline harness.

This module is not a traffic classifier or a production Kubernetes controller.
It converts an already-computed forecast and conservative risk bound into a
bounded desired replica count, while retaining a reactive escape path.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class ScalingObservation:
    current_replicas: int
    min_replicas: int
    max_replicas: int
    observed_rps: float
    forecast_rps: float
    rps_per_replica: float
    attack_risk_upper: float
    max_predictive_step: int


@dataclass(frozen=True)
class ScalingDecision:
    desired_replicas: int
    forecast_target: int
    reactive_target: int
    predictive_step_budget: int
    reason: str


def _replicas_for(rps: float, rps_per_replica: float) -> int:
    return max(0, ceil(max(0.0, rps) / rps_per_replica))


def decide(observation: ScalingObservation) -> ScalingDecision:
    """Return a safe, bounded scale target.

    The upper risk bound limits *predictive* scale-up proportionally. Current
    observed demand retains a reactive path to protect availability. Scale-down
    and min/max replica bounds are deliberately left to the caller/Kubernetes
    stabilization policy in this first prototype.
    """
    values = (
        observation.observed_rps,
        observation.forecast_rps,
        observation.rps_per_replica,
        observation.attack_risk_upper,
    )
    if any(value < 0 for value in values):
        raise ValueError("rates and risk bound must be non-negative")
    if observation.rps_per_replica == 0:
        raise ValueError("rps_per_replica must be positive")
    if observation.min_replicas < 0 or observation.max_replicas < observation.min_replicas:
        raise ValueError("replica bounds are inconsistent")
    if not observation.min_replicas <= observation.current_replicas <= observation.max_replicas:
        raise ValueError("current_replicas must be inside the configured bounds")
    if observation.attack_risk_upper > 1:
        raise ValueError("attack_risk_upper must be between 0 and 1")
    if observation.max_predictive_step < 0:
        raise ValueError("max_predictive_step must be non-negative")

    current = observation.current_replicas
    floor = observation.min_replicas
    ceiling = observation.max_replicas
    forecast_target = min(ceiling, max(floor, _replicas_for(
        observation.forecast_rps, observation.rps_per_replica
    )))
    reactive_target = min(ceiling, max(floor, _replicas_for(
        observation.observed_rps, observation.rps_per_replica
    )))

    # Treat the upper confidence bound conservatively. At risk 0, the full
    # configured predictive step is available; at risk 1, none is available.
    predictive_step_budget = min(
        observation.max_predictive_step,
        ceil(observation.max_predictive_step * (1 - observation.attack_risk_upper)),
    )
    predictive_ceiling = min(ceiling, current + predictive_step_budget)
    desired = max(current, reactive_target, min(forecast_target, predictive_ceiling))
    desired = min(ceiling, max(floor, desired))

    if reactive_target > min(forecast_target, predictive_ceiling):
        reason = "reactive_slo_escape"
    elif forecast_target > current and desired < forecast_target:
        reason = "predictive_scale_bounded_by_risk"
    elif forecast_target > current:
        reason = "predictive_scale"
    else:
        reason = "hold_or_reactive_target"

    return ScalingDecision(
        desired_replicas=desired,
        forecast_target=forecast_target,
        reactive_target=reactive_target,
        predictive_step_budget=predictive_step_budget,
        reason=reason,
    )
