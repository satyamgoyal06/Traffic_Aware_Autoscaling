# Research plan

## Current execution status (2026-11-01)

- **Phase 0:** initial literature scan completed; systematic related-work gap analysis and SPARK reproduction are still outstanding.
- **Phase 1:** implemented synthetic, seeded workload generation; four policy baselines; queue/readiness simulation; JSON/CSV outputs; and a static results page. The first 80-run set is in `results/latest/` and does not establish a DoW saving.
- **Phase 2:** a first local Kubernetes prototype now runs in a two-node `kind` cluster under Docker Desktop. It deploys a CPU-bound HTTP service and replays synthetic traffic while a host-side controller changes Deployment replicas. One 180-second, one-seed legitimate flash run per policy has been recorded. GuardScale did not outperform the reactive or predictive baselines in this exploratory run. KEDA, an in-cluster controller, public-trace replay, multiple seeds, and randomized run order are outstanding.
- **Data:** public traces have not been downloaded. The current run uses documented synthetic scenarios because cluster scheduling traces lack HTTP attack labels and CIC-DDoS datasets do not directly map to replica/cost outcomes.

## Refined problem statement

Kubernetes autoscalers act on load or resource metrics. Predictive controllers can provision capacity before demand arrives, but a load forecast does not encode whether that demand is beneficial, whether its classification is trustworthy, or how much additional resource spend is acceptable. A naive detector can also block a genuine flash crowd, while an attacker can shape requests to resemble ordinary users.

We will design and evaluate a **confidence-aware, budget-bounded predictive scaling policy** for Kubernetes services. It will combine a short-horizon demand forecast with interpretable request/flow behavior signals and an explicit uncertainty/cost policy. The controller will keep a safe minimum service capacity and enforce a configurable replica ceiling or scale-up budget. We will measure the trade-off between SLO protection and resource expenditure under legitimate, malicious, mixed, and adaptive traffic.

This is a research hypothesis, not a novelty claim. SPARK (arXiv:2603.26833, March 2026) already proposes predictive autoscaling plus eBPF/Cilium filtering and refers to HTTP Layer 7 signals. Its paper currently reports a threshold based on HTTP 2xx share, describes PredictKube integration while saying its own model is still being implemented, and gives limited synthetic scenarios. The gap to investigate is rigorous decision-policy and adversarial evaluation under paired/replayed workloads, not “SPARK only sees Layer 3/4” or “nobody combines security and scaling.”

## Primary research question

**RQ1.** Under a fixed SLO and an explicit replica/cost budget, can a confidence-aware predictive policy reduce resource-seconds during attack-shaped demand without materially increasing SLO violations during legitimate flash crowds, compared with reactive, predictive-only, and fixed-threshold security-gated scaling?

### Secondary questions

- **RQ2 (uncertainty):** Does abstaining or taking a bounded action when traffic confidence is low produce a better cost/SLO trade-off than a hard binary classifier gate?
- **RQ3 (adaptation):** How much does performance degrade when attack traffic is deliberately shaped to match the detector’s observable behavior?
- **RQ4 (generalization):** Do the findings hold across distinct workload traces, attack families, and service startup delays?
- **RQ5 (systems cost):** What CPU, memory, decision latency, and control-loop overhead does the added policy introduce?

## Candidate contribution (to validate)

The strongest feasible contribution is a **DoW-specific, budget-constrained control policy and adversarial evaluation**, rather than a new deep model: forecast near-term demand; estimate the chance that added capacity is being induced by attack traffic; translate that uncertainty and an explicit spend/replica budget into a bounded scaling action; preserve a floor and a reactive SLO escape path; then evaluate the cost–availability frontier against adaptive traffic. Uncertainty-aware autoscaling already exists (for example, AAPA and SLO-Scaler), so uncertainty alone is not a novelty claim. The related-work review must determine whether this combination and evaluation gap is actually open.

This aims to improve the evaluation quality over toy classifier accuracy: (1) separate offered demand from successfully served requests, (2) include legitimate flash crowds that resemble attacks, (3) use held-out workload/attack profiles and adaptive evasion, and (4) report cost and SLO jointly with uncertainty. The protocol must be compared against the strongest available open implementation, including SPARK if its artifacts are usable. If this gap is already covered, revise the contribution before claiming novelty.

## Scope and design decisions

- **Service scale:** one HTTP service first. A multi-service graph adds confounders and should be an extension only after the single-service results are sound.
- **Forecasting:** begin with seasonal-naive and EWMA/trend baselines; compare a compact model only if it improves closed-loop outcomes. Do not assume LSTM is inherently better.
- **Traffic signals:** begin with privacy-preserving window aggregates (rate, burstiness, source diversity, endpoint mix, request outcome/latency, repeated-session behavior). Do not use HTTP 2xx share as a legitimacy label: valid attacks can return 2xx and legitimate surges can cause 5xx.
- **Decision policy:** preserve a minimum replica floor; cap maximum replicas; make uncertainty and budget explicit; maintain an emergency reactive path for SLO pressure. A cost/risk policy cannot simply suppress scale on an attack score.
- **Kubernetes integration:** favor a KEDA external scaler or a small controller exposing a custom metric, with an explicit policy layer. Keep the forecast/classifier out of the serving request path.
- **eBPF:** optional experiment/feature source. A local macOS laptop cannot run Linux kernel eBPF directly; use a Linux VM/cluster for any Cilium/eBPF comparison. The base application/request-level path should be portable.
- **Cloud spend:** local replica-seconds and CPU/memory-seconds are the initial cost proxies. A cloud-dollar result requires a separately budgeted, explicitly measured cloud experiment; do not infer dollars from local pod count.

## Threat model

The attacker can send high-volume or low-and-slow HTTP requests to the exposed test service and may vary rate, source fanout (within the simulator), endpoint mix, and timing to evade static heuristics. The attacker cannot compromise the Kubernetes control plane, scaler identity, model artifact, or host. We do not test against live third-party infrastructure. The defense objective is to limit attacker-induced scaling expenditure while maintaining service for legitimate users, not to provide a complete DDoS scrubbing service.

## Phases and gates

### Phase 0 — literature and reproducibility gate

Read the papers in `READING_LIST.md`; inspect SPARK's repository and artifacts; record assumptions, baselines, datasets, and what can be reproduced. Search the proceedings/related work systematically before finalizing a novelty statement. **Gate:** a one-page gap statement with a comparison table and feasible, falsifiable hypotheses.

### Phase 1 — workload and policy simulator

Build deterministic traffic profiles and trace adapters; define controller interfaces; implement reactive, forecast-only, fixed-gate, and proposed policy baselines. Record policy decisions and queue/SLO/cost proxies. Use seeded runs and unit-level invariants for replica bounds, safety floor, and fail-safe behavior. **Gate:** results can be regenerated from a command and config, with raw CSV/JSON output.

### Phase 2 — local Kubernetes prototype

Start a lightweight local Linux Kubernetes environment (kind/minikube) with KEDA, Prometheus/metrics, one instrumented HTTP workload, and an isolated load generator. Compare actual pod readiness/startup and request latency against simulator estimates. **Gate:** stable repeatable baseline runs, resource limit established, and all traffic remains local.

### Phase 3 — defensible benchmark

Replay public traces where their semantics fit, and add scripted/synthetic application-level scenarios with exact labels. Use time-ordered and scenario-held-out splits; tune on development scenarios only. Evaluate all policies on identical arrival traces, with multiple seeds and confidence intervals. **Gate:** pre-registered comparisons, ablations, and negative results reported.

### Phase 4 — adaptive evaluation and artifact

Construct an adaptive attacker that searches within a declared traffic budget to match benign observable features; report degradation and cost/availability frontier. Package installable KEDA integration, documentation, configs, data provenance, and an evidence-backed results site/dashboard. **Gate:** independent reproduction from a clean checkout.

## Publication standard

A top-conference/journal submission is an aspiration, not something a project plan can guarantee. To make a serious submission plausible: name a narrow claim; compare to closest systems; distinguish attack detection from policy utility; avoid train/test leakage; report repeated-run distributions and confidence intervals; expose code/config/trace transformation scripts; discuss failure modes and resource overhead; and reproduce the full path from raw inputs to figures. Do not report only accuracy, best seeds, or simulated “cloud dollars.”

## Showcase strategy

Build a small static results site only after repeatable measurements exist. It should show the system diagram, workload timeline, replica timeline, p50/p95/p99 latency, SLO violations, replica-seconds, policy confidence/actions, and confidence intervals. Link each chart to a versioned machine-readable result and the command/config that generated it. A polished demo can include a live local replay, but the site must clearly label simulated and Kubernetes-measured results separately.
