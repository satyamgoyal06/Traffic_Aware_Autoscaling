"""Replay a synthetic trace against an isolated local Kubernetes service."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import math
import subprocess
import time
from pathlib import Path
from statistics import mean, median
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from .policy import ScalingObservation, decide
from .workload import SCENARIOS, estimate_forecast, make_scenario


def _kubectl(*args: str) -> str:
    return subprocess.run(["kubectl", *args], check=True, capture_output=True,
                          text=True).stdout


def _replicas() -> tuple[int, int]:
    payload = json.loads(_kubectl("get", "deployment", "guardscale-demo", "-o", "json"))
    return int(payload["spec"].get("replicas", 0)), int(payload["status"].get("readyReplicas", 0))


def _request(url: str) -> tuple[float, int]:
    started = time.perf_counter()
    try:
        with urlopen(url, timeout=8) as response:
            response.read()
            return (time.perf_counter() - started) * 1000, response.status
    except (URLError, TimeoutError, OSError):
        return (time.perf_counter() - started) * 1000, 0


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)]


def _target(policy: str, current: int, observed: float, forecast: float,
            risk: float, rps_per_replica: float, maximum: int) -> tuple[int, str]:
    floor = 1
    if policy == "reactive":
        return min(maximum, max(floor, math.ceil(observed / rps_per_replica))), "reactive"
    if policy == "predictive":
        return min(maximum, max(floor, math.ceil(forecast / rps_per_replica))), "forecast"
    observation = ScalingObservation(
        current_replicas=current, min_replicas=floor, max_replicas=maximum,
        observed_rps=observed, forecast_rps=forecast,
        rps_per_replica=rps_per_replica,
        attack_risk_upper=min(1.0, risk + 0.05), max_predictive_step=3,
    )
    decision = decide(observation)
    return decision.desired_replicas, decision.reason


def run(args: argparse.Namespace) -> dict:
    rows = make_scenario(args.scenario, args.seed, args.duration)
    base_url = args.url.rstrip("/")
    # Wait for the service before starting the recorded trace.
    deadline = time.monotonic() + 90
    while True:
        try:
            with urlopen(f"{base_url}/healthz", timeout=2) as response:
                if response.status == 200:
                    break
        except (URLError, TimeoutError, OSError):
            if time.monotonic() >= deadline:
                raise RuntimeError(f"service did not become ready at {base_url}")
            time.sleep(1)

    _kubectl("scale", "deployment/guardscale-demo", "--replicas=1")
    history: list[float] = []
    output_rows: list[dict] = []
    total_requests = 0
    errors = 0
    scale_actions = 0
    current = 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in rows:
            forecast = estimate_forecast(history, horizon=20)
            target, reason = _target(args.policy, current, row.offered_rps,
                                     forecast, row.risk_score, args.rps_per_replica,
                                     args.max_replicas)
            started = time.monotonic()
            if target != current:
                _kubectl("scale", "deployment/guardscale-demo", f"--replicas={target}")
                current = target
                scale_actions += 1

            count = max(1, round(row.offered_rps))
            futures: list[concurrent.futures.Future] = []
            # Pace arrivals across the second rather than sending one artificial
            # burst. Offered traffic remains the known trace rate; completion,
            # errors, and client latency are measured from real HTTP requests.
            for index in range(count):
                due = started + index / count
                delay = due - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                futures.append(pool.submit(_request, base_url))
            responses = [future.result() for future in futures]
            latencies = [latency for latency, status in responses if status == 200]
            window_errors = sum(status != 200 for _, status in responses)
            total_requests += count
            errors += window_errors
            desired, ready = _replicas()
            elapsed = time.monotonic() - started
            if elapsed < 1:
                time.sleep(1 - elapsed)

            output_rows.append({
                "second": row.second,
                "scenario": args.scenario,
                "seed": args.seed,
                "policy": args.policy,
                "offered_rps": round(row.offered_rps, 3),
                "forecast_rps": round(forecast, 3),
                "risk_heuristic": round(row.risk_score, 4),
                "decision_reason": reason,
                "desired_replicas": desired,
                "ready_replicas": ready,
                "requests_sent": count,
                "http_errors": window_errors,
                "mean_latency_ms": round(mean(latencies), 3) if latencies else 0,
                "p95_latency_ms": round(_percentile(latencies, 0.95), 3),
                "window_wall_seconds": round(elapsed, 3),
                "evidence_type": "local_kubernetes_measurement",
                "traffic_source": "synthetic_trace",
            })
            history.append(row.offered_rps)

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    payload = {
        "scenario": args.scenario,
        "seed": args.seed,
        "policy": args.policy,
        "duration_seconds": args.duration,
        "requests_sent": total_requests,
        "http_errors": errors,
        "error_rate_pct": round(100 * errors / total_requests, 3) if total_requests else 0,
        "scale_actions": scale_actions,
        "mean_window_p95_latency_ms": round(mean([r["p95_latency_ms"] for r in output_rows]), 3),
        "median_window_p95_latency_ms": round(median([r["p95_latency_ms"] for r in output_rows]), 3),
        "max_window_p95_latency_ms": round(max(r["p95_latency_ms"] for r in output_rows), 3),
        "trace_target_replica_seconds": sum(r["desired_replicas"] for r in output_rows),
        "trace_ready_replica_seconds": sum(r["ready_replicas"] for r in output_rows),
        "run_wall_seconds": round(sum(r["window_wall_seconds"] for r in output_rows), 3),
        "rps_per_replica_assumption": args.rps_per_replica,
        "max_replicas": args.max_replicas,
        "workers": args.workers,
        "work_iterations_per_request": 12000,
        "evidence_type": "local_kubernetes_measurement",
        "traffic_source": "synthetic_trace",
        "rows_csv": str(destination),
    }
    summary_path = destination.with_suffix(".json")
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="legitimate_flash")
    parser.add_argument("--policy", choices=("reactive", "predictive", "guardscale"), default="guardscale")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--rps-per-replica", type=float, default=60)
    parser.add_argument("--max-replicas", type=int, default=6)
    parser.add_argument("--workers", type=int, default=96)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--out", default="results/kubernetes/guardscale.csv")
    args = parser.parse_args()
    if args.duration < 180:
        parser.error("duration must be at least 180 seconds")
    if args.rps_per_replica <= 0 or args.max_replicas < 1 or args.workers < 1:
        parser.error("capacity and concurrency settings must be positive")
    endpoint = urlparse(args.url)
    if endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost"} or endpoint.port != 8080:
        parser.error("load is restricted to the local demo service at http://127.0.0.1:8080")
    result = run(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
