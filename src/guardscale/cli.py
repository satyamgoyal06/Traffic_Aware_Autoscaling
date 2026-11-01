from __future__ import annotations

import argparse

from .benchmark import run_benchmark
from .policy import ScalingObservation, decide
from .workload import SCENARIOS, make_scenario, write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardscale", description="GuardScale offline policy prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("decision", help="show one bounded scaling decision")
    demo.add_argument("--current", type=int, default=2)
    demo.add_argument("--min", dest="min_replicas", type=int, default=1)
    demo.add_argument("--max", dest="max_replicas", type=int, default=12)
    demo.add_argument("--observed-rps", type=float, default=80)
    demo.add_argument("--forecast-rps", type=float, default=240)
    demo.add_argument("--rps-per-replica", type=float, default=50)
    demo.add_argument("--risk-upper", type=float, default=0.2)
    demo.add_argument("--max-predictive-step", type=int, default=4)

    generate = commands.add_parser("generate", help="write one seeded synthetic workload CSV")
    generate.add_argument("--scenario", choices=SCENARIOS, required=True)
    generate.add_argument("--seed", type=int, default=1)
    generate.add_argument("--duration", type=int, default=420)
    generate.add_argument("--out", required=True)

    benchmark = commands.add_parser("benchmark", help="run paired synthetic policy comparisons and make a results page")
    benchmark.add_argument("--seeds", type=int, default=5)
    benchmark.add_argument("--duration", type=int, default=420)
    benchmark.add_argument("--out", default="results/latest")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "generate":
        rows = make_scenario(args.scenario, args.seed, args.duration)
        write_csv(args.out, rows)
        print(f"wrote {len(rows)} windows to {args.out}")
        return 0
    if args.command == "benchmark":
        payload = run_benchmark(args.out, args.seeds, args.duration)
        print(f"completed {len(payload['runs'])} paired policy runs")
        print(f"results: {args.out}/results.json")
        print(f"results page: {args.out}/index.html")
        return 0

    observation = ScalingObservation(
        current_replicas=args.current,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        observed_rps=args.observed_rps,
        forecast_rps=args.forecast_rps,
        rps_per_replica=args.rps_per_replica,
        attack_risk_upper=args.risk_upper,
        max_predictive_step=args.max_predictive_step,
    )
    decision = decide(observation)
    print(f"desired_replicas={decision.desired_replicas}")
    print(f"forecast_target={decision.forecast_target}")
    print(f"reactive_target={decision.reactive_target}")
    print(f"predictive_step_budget={decision.predictive_step_budget}")
    print(f"reason={decision.reason}")
    return 0
