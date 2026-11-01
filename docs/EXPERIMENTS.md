# Experimental protocol

## Baselines

All policies receive the same offered request-arrival sequence and service configuration.

1. **Reactive:** request-rate or CPU/queue threshold scaling, with measured actuation/readiness delay.
2. **Predictive-only:** forecast-driven scaling with no traffic-risk input.
3. **Static security gate:** predictive scaling with a fixed traffic-risk threshold.
4. **Confidence/budget policy (candidate):** proposed risk-aware action with uncertainty, replica/spend cap, safe floor, and reactive SLO escape path.
5. **Oracle bounds (analysis only):** perfect future demand and/or perfect traffic labels to estimate headroom; never presented as deployable baselines.

Where artifacts are available, add SPARK's implementation as a baseline or reproduce its design faithfully. Clearly note any unavailable commercial dependency and do not compare against an imagined version.

## Workload matrix

- Steady low and steady high demand.
- Smooth ramp and sharp legitimate flash crowd.
- Periodic/bursty real-trace-derived intensity.
- High-rate attack, low-and-slow attack, endpoint-concentrated request pattern, and mixed benign/attack load.
- Legitimate flash crowd with diversity/regularity overlapping attack features (false-positive challenge).
- Adaptive attacker that tunes rate, source fanout, timing, and endpoint distribution against published features while staying within a fixed request budget.
- Cold start and multiple service startup delays; workload changes and detector drift.

The traffic generator must distinguish **offered** requests from **admitted**, **completed**, **failed**, and **timed out** requests. Never use successful-response fraction as the sole ground-truth legitimacy label.

## Primary metrics

- **SLO:** p50/p95/p99 request latency; timeout/error rate; fraction/time outside the declared latency/error SLO; time to recover.
- **Resource/cost proxy:** replica-seconds above minimum, CPU-seconds, memory-seconds, scale actions, peak replicas, and wasted capacity. Cloud dollars only from actual metered cloud invoices/pricing records.
- **Security/policy:** attack-induced replica-seconds; legitimate spike capacity shortfall; false scale suppression; attack pass-through; detection delay; precision/recall at the *decision window* level; calibration/abstention rate.
- **Controller overhead:** CPU, memory, per-decision latency, missed update rate, and control-plane/API load.

## Controls and reporting

- Pin CPU/memory limits and the cluster runtime version. Record machine model, host utilization, Docker VM resources, cluster config, image digests, and startup latency.
- Run policies in randomized order on paired traces. Repeat independent workload seeds and report median, dispersion, 95% confidence intervals, and effect sizes.
- Select thresholds/models on development traces only. Preserve held-out days/workloads and whole attack scenarios for final evaluation.
- Ablate forecast, risk input, uncertainty handling, hard cap, and emergency path one at a time.
- Report trade-off curves (attack cost versus legitimate SLO violations), not a single cherry-picked threshold.
- Include CPU-load interference checks and run enough warm-up/steady state to separate startup effects from policy effects.
- Save raw per-window telemetry as append-only CSV/JSON, and derive plots/tables with versioned scripts.

## Local resource plan

The development host is an Apple Silicon Mac with 8 CPU cores and 16 GiB RAM. Docker Desktop reports an ARM64 Linux VM with 8 CPUs and about 7.8 GiB. A two-node kind cluster is running, with a localhost-only NodePort. The demo workload is limited to 500m CPU and 192 MiB per replica, and the replay caps desired replicas at six. eBPF/Cilium needs a Linux kernel environment, normally via the Docker Desktop Linux VM or another Linux host; macOS itself is not an eBPF target. Avoid downloading large traces until the schema adapters are selected.

## Phase 1 implementation and first result

Implemented under `src/guardscale/`: seeded workload generation; a causal two-window trend forecast; reactive, predictive-only, fixed-risk-gate, and risk-bounded policies; a simplified queue/readiness simulator; paired repeated runs; CSV/JSON outputs; and a static report page. Current scenarios are all synthetic and intentionally include legitimate flash and lookalike traffic alongside simple and feature-mimicking attacks. The “risk score” is an exposed two-feature heuristic for diversity and timing regularity, not a trained detector.

The first checked-in run is 4 scenarios × 5 paired seeds × 4 policies = 80 runs in `results/latest/`. It does **not** support a resource-savings claim: in the attack-flood scenario the proposed risk-bounded policy averages 1,233 desired replica-seconds versus 1,216 for predictive-only, with nearly identical estimated p95 latency (11.71s versus 11.76s). In the adaptive-attack scenario it likewise tracks predictive-only closely. On legitimate flash load its estimated SLO violation fraction is the same as predictive-only (26.25%) and lower than reactive (41.60%), but all these values come from a toy queue model. They are a useful negative baseline: the present policy has not shown a DoW benefit.

The report includes normal-approximation 95% confidence intervals across five seeds. That is only an initial repeated-run summary; these intervals do not capture uncertainty in simulator assumptions, and five seeds are not enough for strong statistical claims. Generated traffic CSVs, run outputs, policy decisions, and assumptions accompany the report.

## Phase 2 initial local Kubernetes run

The isolated cluster, workload, replay runner, and reproduction commands are documented in `deploy/kind/README.md`. The service performs 12,000 SHA-256 operations per request with a 500m CPU limit. The runner replays one 180-second `legitimate_flash` trace (seed 1) against the local service for reactive, predictive-only, and GuardScale policies. It uses the known synthetic scenario heuristic and a host-side `kubectl` loop, then records actual request latencies, HTTP errors, and Ready pod counts. It is not a trained classifier or in-cluster operator.

The initial comparison is in `results/kubernetes/index.html`, with per-window CSVs and JSON run summaries beside it. Each policy received the same 20,548-request offered trace and recorded zero HTTP errors. Trace-target replica-seconds were 446 (reactive), 474 (predictive), and 562 (GuardScale). Mean per-window p95 latency was 10.845 ms, 11.513 ms, and 15.881 ms respectively; the worst GuardScale window was 1,067.575 ms. This is one seed, fixed policy order, and one synthetic legitimate scenario. It is exploratory evidence only, shows no GuardScale win here, and does not establish general performance or security claims. Trace-target replica-seconds sum requested replicas across the one-second trace bins; they are not billed runtime. The page reports means/medians of window-level p95s, not a pooled request p95.

## Evidence labels

Every artifact should say whether a result is **synthetic simulation**, **public-trace replay**, **local Kubernetes measurement**, or **cloud-metered cost**. These are different evidence levels and must not be blended in charts or prose.
