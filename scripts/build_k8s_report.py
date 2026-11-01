#!/usr/bin/env python3
"""Build a small static report from calibrated local Kubernetes runs."""

from __future__ import annotations

import csv
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/kubernetes"


def main() -> None:
    summaries = []
    for csv_path in sorted(OUT.glob("legitimate_flash_*_seed*.csv")):
        summary_path = csv_path.with_suffix(".json")
        if not summary_path.exists():
            continue
        run_metadata = json.loads(summary_path.read_text(encoding="utf-8"))
        if run_metadata.get("work_iterations_per_request") != 12000:
            continue  # Exclude the explicitly uncalibrated pilot.
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        latencies = [float(row["p95_latency_ms"]) for row in rows]
        desired = [int(row["desired_replicas"]) for row in rows]
        ready = [int(row["ready_replicas"]) for row in rows]
        run_metadata.pop("desired_replica_seconds", None)
        run_metadata["trace_target_replica_seconds"] = sum(desired)
        run_metadata["trace_ready_replica_seconds"] = sum(ready)
        run_metadata["mean_window_p95_latency_ms"] = round(statistics.mean(latencies), 3)
        run_metadata["median_window_p95_latency_ms"] = round(statistics.median(latencies), 3)
        run_metadata["max_window_p95_latency_ms"] = round(max(latencies), 3)
        run_metadata["summary_derived_from_csv"] = True
        summary_path.write_text(json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8")
        summaries.append({
            "policy": run_metadata["policy"],
            "seed": run_metadata["seed"],
            "scenario": run_metadata["scenario"],
            "windows": len(rows),
            "requests": run_metadata["requests_sent"],
            "http_errors": run_metadata["http_errors"],
            "trace_target_replica_seconds": sum(desired),
            "mean_ready_replicas": round(statistics.mean(ready), 3),
            "mean_window_p95_ms": round(statistics.mean(latencies), 3),
            "median_window_p95_ms": round(statistics.median(latencies), 3),
            "max_window_p95_ms": round(max(latencies), 3),
            "windows_above_2s_p95": sum(value > 2000 for value in latencies),
            "scale_actions": run_metadata["scale_actions"],
            "csv": csv_path.name,
        })
    summaries.sort(key=lambda item: (item["scenario"], item["policy"]))
    (OUT / "comparison.json").write_text(json.dumps({
        "evidence_type": "local_kubernetes_measurement",
        "traffic_source": "synthetic_trace",
        "seed_count": len({item["seed"] for item in summaries}),
        "runs": summaries,
    }, indent=2) + "\n", encoding="utf-8")

    body_rows = []
    for item in summaries:
        values = (
            item["policy"], item["seed"], item["requests"], item["http_errors"],
            item["trace_target_replica_seconds"], item["mean_ready_replicas"],
            item["mean_window_p95_ms"], item["median_window_p95_ms"],
            item["max_window_p95_ms"], item["scale_actions"],
        )
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in values)
        cells += f'<td><a href="{html.escape(item["csv"])}">CSV</a></td>'
        body_rows.append(f"<tr>{cells}</tr>")
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GuardScale · Local Kubernetes measurements</title>
<style>
:root{--ink:#10212b;--muted:#53656d;--paper:#f2f5f3;--card:#fff;--line:#dbe4e1;--teal:#147d73;--orange:#d97742}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1200px;margin:0 auto;padding:40px 24px 80px}.eyebrow{color:var(--teal);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.12em}
h1{font-size:clamp(36px,6vw,60px);line-height:1.02;letter-spacing:-.045em;margin:10px 0 14px}h2{font-size:22px;margin:0 0 12px}
p{color:var(--muted);max-width:900px}.callout{background:#fff2d9;border:1px solid #eed8ad;border-radius:14px;padding:14px 18px;margin:24px 0;color:#5d491c}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin:16px 0;box-shadow:0 8px 28px #18352a0a}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:right;border-bottom:1px solid var(--line);padding:10px 12px;white-space:nowrap}th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}th:first-child,td:first-child{text-align:left}.foot{font-size:13px;color:var(--muted)}code{background:#eef2f0;padding:2px 5px;border-radius:4px}
</style></head><body><main>
<div class="eyebrow">GuardScale · Local Kubernetes measurement</div><h1>First cluster run</h1>
<p>One seeded synthetic legitimate flash trace was replayed against a CPU-bound HTTP service in a two-node kind cluster. The host-side prototype changed the Kubernetes Deployment replica count and recorded client request latency and pod readiness.</p>
<div class="callout"><strong>Evidence limits:</strong> this is one seed and one synthetic scenario on a local Docker Desktop cluster. It is an exploratory systems measurement, not a statistically supported performance claim, an attack-detection result, or cloud cost evidence. The 2-second comparison uses each one-second window’s request p95.</div>
<section class="card"><h2>Matched trace, different policies</h2><div class="table-wrap"><table><thead><tr>
<th>Policy</th><th>Seed</th><th>Requests</th><th>HTTP errors</th><th>Target replica-seconds*</th><th>Mean Ready replicas</th><th>Mean of window p95 (ms)</th><th>Median window p95 (ms)</th><th>Worst window p95 (ms)</th><th>Scale actions</th><th>Raw trace</th>
</tr></thead><tbody>__ROWS__</tbody></table></div></section>
<section class="card"><h2>How to read this</h2><p>The offered trace is identical across policies (seed 1, 180 seconds, 20,548 requests). The current GuardScale decision policy uses more target replica-seconds than either baseline in this single run. Its worst window also has a latency spike. This is a negative result for the present configuration, not evidence of a benefit.</p>
<p>* Target replica-seconds are the sum of requested replica counts across trace windows. They are a workload-time resource proxy, not metered node time or a cloud invoice. Mean and median p95 columns summarize per-window p95 values; they are not the p95 of all requests pooled together.</p>
<p>The app performs 12,000 SHA-256 operations per request. CPU/memory limits, scenario, seed, and workload trace are recorded in the CSV and paired JSON summaries. The runner uses a host-side <code>kubectl</code> loop; it is not yet an in-cluster controller, KEDA integration, or production operator.</p></section>
<section class="card"><h2>Reproduce</h2><pre><code>PYTHONPATH=src python3 -m guardscale.k8s_benchmark --scenario legitimate_flash --policy reactive --seed 1 --duration 180 --out results/kubernetes/reactive.csv
PYTHONPATH=src python3 -m guardscale.k8s_benchmark --scenario legitimate_flash --policy predictive --seed 1 --duration 180 --out results/kubernetes/predictive.csv
PYTHONPATH=src python3 -m guardscale.k8s_benchmark --scenario legitimate_flash --policy guardscale --seed 1 --duration 180 --out results/kubernetes/guardscale.csv</code></pre></section>
<p class="foot">Generated from calibrated run CSVs by <code>scripts/build_k8s_report.py</code>. Raw per-window measurements are linked above.</p>
</main></body></html>""".replace("__ROWS__", "\n".join(body_rows))
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {OUT / 'index.html'} with {len(summaries)} runs")


if __name__ == "__main__":
    main()
