# GuardScale

**Traffic-aware, budget-bounded predictive autoscaling for Kubernetes.**

GuardScale studies a systems problem: a forecast can tell a scaler that demand is about to rise, but the forecast alone cannot tell whether paying to add capacity is useful or economically safe. The project will evaluate a policy that combines demand prediction, traffic-risk uncertainty, and an explicit capacity budget while preserving service-level objectives (SLOs).

This is a research prototype. It does not claim attack detection, cloud savings, or production readiness. It now includes a CPU-only synthetic simulator and an initial local Kubernetes measurement harness.

## Research question

Can a confidence-aware, budget-bounded scaling policy reduce resource expenditure under attack-shaped or ambiguous load while keeping legitimate flash-crowd SLO violations close to predictive-only scaling?

The research contribution is deliberately framed as a question, not a claim of novelty. A recent preprint, SPARK, already combines predictive scaling with eBPF/Cilium security controls and reports Layer 7 signals. GuardScale therefore will not claim novelty merely from combining network and application signals. We will first reproduce the closest claims and establish a specific gap through a literature review.

## Repository status

- Research scope, threat model, dataset shortlist, and benchmark protocol: `docs/`.
- Local prototype: a deterministic bounded scaling decision primitive in `src/guardscale/policy.py`, an offline trace simulator, and a host-side Kubernetes replay runner.
- Synthetic simulator: paired comparisons, five seeds per scenario, raw generated CSV traces, machine-readable output, and a static results page in `results/latest/`.
- Local Kubernetes prototype: a two-node `kind` cluster, CPU-bound HTTP workload, and replay runner are in `deploy/` and `src/guardscale/k8s_benchmark.py`.
- Initial local Kubernetes measurements: one 180-second synthetic flash trace per policy and one seed; raw CSV/JSON and a report are in `results/kubernetes/`. These exploratory results show no GuardScale advantage in the current configuration.
- KEDA/in-cluster controller, public-trace replay, multi-seed cluster evaluation, and cloud-metered experiments remain future work.

## Quick start

Python 3.11+ is the target runtime. The initial policy prototype uses only the standard library, so it can run on a laptop without a GPU or paid cloud account.

```sh
PYTHONPATH=src python3 -m guardscale --help
PYTHONPATH=src python3 -m guardscale decision --risk-upper 0.8
PYTHONPATH=src python3 -m guardscale benchmark --seeds 5 --out results/latest
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The local Kubernetes setup and replay commands are documented in [`deploy/kind/README.md`](deploy/kind/README.md). The initial measured results are in [`results/kubernetes/index.html`](results/kubernetes/index.html).

The checked-in `results/latest/` output is a synthetic simulator run. It is not a Kubernetes benchmark and the latency/cost-like values are model estimates and replica-time proxies.

## Project map

- `docs/RESEARCH_PLAN.md` — refined problem statement, hypotheses, threat model, research risks, and phased plan.
- `docs/DATASETS.md` — trustworthy workload/security data sources and how each can and cannot support our claims.
- `docs/EXPERIMENTS.md` — baselines, metrics, controls, statistical reporting, and local-cluster measurements.
- `docs/READING_LIST.md` — primary papers and official references to read and annotate.
- `src/guardscale/` — implementation.
- `data/` — place downloaded datasets here; source datasets are not checked in.
- `results/` — raw run outputs and derived figures; never hand-edit raw measurements.

## Safety and reproducibility

All live load generation is restricted to the isolated local service at `127.0.0.1:8080`; no external target is contacted. Run metadata records scenario, seed, policy, and workload assumptions. Before public release, add a source revision identifier and repeat cluster runs with randomized policy order and multiple seeds. Public datasets are downloaded only from their maintainers and cited according to their terms.
