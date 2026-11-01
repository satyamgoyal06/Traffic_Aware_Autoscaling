"""Repeatable synthetic policy comparison and static results page."""

from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .simulator import SimulationConfig, simulate
from .workload import SCENARIOS, make_scenario, read_csv, write_csv

POLICIES = ("reactive", "predictive", "fixed_gate", "guardscale")


def _mean_ci(values: list[float]) -> dict[str, float]:
    mean = statistics.mean(values)
    if len(values) < 2:
        return {"mean": mean, "ci95": 0.0}
    return {"mean": mean, "ci95": 1.96 * statistics.stdev(values) / math.sqrt(len(values))}


def _aggregate(runs: list[dict]) -> list[dict]:
    metrics = (
        "replica_seconds", "mean_desired_replicas", "max_ready_replicas", "scale_actions",
        "legitimate_requests_slo_violation_pct", "legitimate_request_p95_latency_estimate_seconds",
        "attack_window_replica_seconds",
    )
    groups: dict[tuple[str, str], list[dict]] = {}
    for run in runs:
        groups.setdefault((run["scenario"], run["policy"]), []).append(run)
    output = []
    for (scenario, policy), group in sorted(groups.items()):
        row = {"scenario": scenario, "policy": policy, "n": len(group)}
        for metric in metrics:
            row[metric] = _mean_ci([float(item[metric]) for item in group])
        output.append(row)
    return output


def _fmt(value: dict[str, float], digits: int = 2) -> str:
    return f"{value['mean']:.{digits}f} ± {value['ci95']:.{digits}f}"


def _chart_svg(aggregate: list[dict], scenario: str, metric: str, title: str,
               max_value: float, color: str, width: int = 680, height: int = 270) -> str:
    data = [row for row in aggregate if row["scenario"] == scenario]
    margin_left, margin_right, margin_top, margin_bottom = 70, 20, 28, 48
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    bar_w = plot_w / max(1, len(data)) * 0.48
    items = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
             f'<text x="{margin_left}" y="19" class="chart-title">{escape(title)}</text>',
             f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{width-margin_right}" y2="{margin_top+plot_h}" class="axis"/>']
    for i, row in enumerate(data):
        value = row[metric]["mean"]
        ci = row[metric]["ci95"]
        x = margin_left + (i + 0.5) * plot_w / max(1, len(data))
        h = max(0, min(plot_h, value / max_value * plot_h))
        y = margin_top + plot_h - h
        bar_x = x - bar_w / 2
        items.append(f'<rect x="{bar_x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="5" fill="{color}" opacity=".88"/>')
        upper_y = margin_top + plot_h - min(plot_h, (value + ci) / max_value * plot_h)
        lower_y = margin_top + plot_h - max(0, (value - ci) / max_value * plot_h)
        items.append(f'<line x1="{x:.1f}" y1="{upper_y:.1f}" x2="{x:.1f}" y2="{lower_y:.1f}" stroke="#10212b" stroke-width="2"/><line x1="{x-6:.1f}" y1="{upper_y:.1f}" x2="{x+6:.1f}" y2="{upper_y:.1f}" stroke="#10212b" stroke-width="2"/><line x1="{x-6:.1f}" y1="{lower_y:.1f}" x2="{x+6:.1f}" y2="{lower_y:.1f}" stroke="#10212b" stroke-width="2"/>')
        label = row["policy"].replace("_", " ")
        items.append(f'<text x="{x:.1f}" y="{height-22}" text-anchor="middle" class="axis-label">{escape(label)}</text>')
    items.append("</svg>")
    return "".join(items)


def write_site(path: Path, payload: dict) -> None:
    aggregate = payload["aggregate"]
    available = sorted({row["scenario"] for row in aggregate})
    options = "".join(f'<option value="{escape(name)}">{escape(name.replace("_", " "))}</option>' for name in available)
    largest_cost = max(row["replica_seconds"]["mean"] + row["replica_seconds"]["ci95"] for row in aggregate) or 1
    largest_slo = max(row["legitimate_requests_slo_violation_pct"]["mean"] + row["legitimate_requests_slo_violation_pct"]["ci95"] for row in aggregate) or 1
    rows_html = []
    for row in aggregate:
        rows_html.append(
            "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in (
                row["scenario"].replace("_", " "), row["policy"].replace("_", " "), row["n"],
                _fmt(row["replica_seconds"], 0),
                _fmt(row["legitimate_requests_slo_violation_pct"]),
                _fmt(row["legitimate_request_p95_latency_estimate_seconds"]),
                _fmt(row["attack_window_replica_seconds"], 0),
            )) + "</tr>"
        )
    chart_template = {
        "cost": _chart_svg(aggregate, available[0], "replica_seconds", "Replica-seconds (lower uses fewer resources)", largest_cost, "#147d73"),
        "slo": _chart_svg(aggregate, available[0], "legitimate_requests_slo_violation_pct", "Legitimate requests outside 2s latency target (lower is better)", largest_slo, "#d97742"),
    }
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GuardScale · Local benchmark</title>
<style>
:root{{--ink:#10212b;--muted:#53656d;--paper:#f2f5f3;--card:#fff;--line:#dbe4e1;--teal:#147d73;--orange:#d97742}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1120px;margin:0 auto;padding:42px 24px 80px}}.eyebrow{{color:var(--teal);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.12em}}
h1{{font-size:clamp(36px,6vw,64px);line-height:1.02;letter-spacing:-.045em;margin:10px 0 14px}}h2{{font-size:22px;letter-spacing:-.02em;margin:0 0 12px}}
p{{color:var(--muted);max-width:850px}}.callout{{background:#fff2d9;border:1px solid #eed8ad;border-radius:14px;padding:14px 18px;margin:24px 0;color:#5d491c}}
.meta,.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:22px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 8px 28px #18352a0a}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.chart svg{{width:100%;height:auto;overflow:visible}}.chart-title{{fill:var(--ink);font-size:13px;font-weight:700}}.axis{{stroke:#aab8b4}}.axis-label{{fill:var(--muted);font-size:11px}}
select{{border:1px solid var(--line);background:#fff;border-radius:10px;padding:10px 12px;font:inherit;color:var(--ink);margin:2px 0 16px}}
.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{text-align:left;border-bottom:1px solid var(--line);padding:10px 12px;white-space:nowrap}}th{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}td:nth-child(n+4){{text-align:right}}
.foot{{font-size:13px;color:var(--muted)}}code{{background:#eef2f0;padding:2px 5px;border-radius:4px}}@media(max-width:760px){{main{{padding:26px 16px 60px}}.charts{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="eyebrow">Research prototype · reproducible simulation</div><h1>GuardScale</h1>
<p>A matched-trace comparison of reactive, predictive, fixed-gate and risk-bounded predictive scaling policies under legitimate and attack-shaped load.</p>
<div class="callout"><strong>Evidence boundary:</strong> these are synthetic simulator results, not Kubernetes measurements, real attack detection results, or cloud-dollar savings. Traffic features and service capacity are simplified assumptions.</div>
<div class="meta"><div class="card"><strong>Run</strong><br>{escape(payload['run_id'])}</div><div class="card"><strong>Machine</strong><br>{escape(payload['machine'])}</div><div class="card"><strong>Runs per policy/scenario</strong><br>{payload['seeds_per_scenario']} paired seeds</div></div>
<section class="card"><h2>Compare policies</h2><label for="scenario"><strong>Workload scenario</strong></label><br><select id="scenario">{options}</select>
<div class="charts"><div class="chart" id="cost">{chart_template['cost']}</div><div class="chart" id="slo">{chart_template['slo']}</div></div>
<p class="foot">Bars show the mean across paired seeds; whiskers show a normal-approximation 95% confidence interval. Replica-seconds are a local capacity proxy, not dollars. Latency is estimated from a simple queue model.</p></section>
<section class="card" style="margin-top:16px"><h2>Run table</h2><div class="table-wrap"><table><thead><tr><th>Scenario</th><th>Policy</th><th>n</th><th>Replica-seconds</th><th>SLO violation %</th><th>Estimated p95 latency (s)</th><th>Attack-window replica-seconds</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div></section>
<section class="grid"><div class="card"><h2>What the scenarios mean</h2><p><strong>Legitimate flash:</strong> varied source/timing signals. <strong>Attack flood:</strong> concentrated, regular traffic. <strong>Adaptive attack:</strong> attack traffic mimics the simple behavior features. <strong>Legitimate lookalike:</strong> real demand also resembles those features, exposing false positives.</p></div><div class="card"><h2>Reproduce</h2><p>From the repository root run <code>PYTHONPATH=src python3 -m guardscale benchmark --seeds {payload['seeds_per_scenario']} --out results/latest</code>. Full per-run outputs and the assumptions are included beside this page.</p></div></section>
<p class="foot">Generated {escape(payload['generated_at'])} · Controller design and data limitations: <a href="../../docs/EXPERIMENTS.md">experiment protocol</a>.</p>
<script id="benchmark-data" type="application/json">{data_json}</script>
<script>
const D=JSON.parse(document.getElementById('benchmark-data').textContent);const sel=document.getElementById('scenario');
function redraw(){{const s=sel.value;const rows=D.aggregate.filter(r=>r.scenario===s);const maxCost=Math.max(1,...rows.map(r=>r.replica_seconds.mean+r.replica_seconds.ci95));const maxSlo=Math.max(1,...rows.map(r=>r.legitimate_requests_slo_violation_pct.mean+r.legitimate_requests_slo_violation_pct.ci95));
document.getElementById('cost').innerHTML=chart(rows,'replica_seconds','Replica-seconds (lower uses fewer resources)',maxCost,'#147d73');document.getElementById('slo').innerHTML=chart(rows,'legitimate_requests_slo_violation_pct','Legitimate requests outside 2s latency target (lower is better)',maxSlo,'#d97742');}}
function chart(rows,key,title,max,color){{const w=680,h=270,l=70,r=20,t=28,b=48,pw=w-l-r,ph=h-t-b,bw=pw/rows.length*.48;let x=`<svg viewBox="0 0 ${{w}} ${{h}}" role="img"><text x="${{l}}" y="19" class="chart-title">${{title}}</text><line x1="${{l}}" y1="${{t+ph}}" x2="${{w-r}}" y2="${{t+ph}}" class="axis"/>`;rows.forEach((o,i)=>{{let m=o[key].mean,c=o[key].ci95,cx=l+(i+.5)*pw/rows.length,bh=Math.max(0,m/max*ph),y=t+ph-bh,uy=t+ph-Math.min(ph,(m+c)/max*ph),ly=t+ph-Math.max(0,(m-c)/max*ph);x+=`<rect x="${{cx-bw/2}}" y="${{y}}" width="${{bw}}" height="${{bh}}" rx="5" fill="${{color}}" opacity=".88"/><line x1="${{cx}}" y1="${{uy}}" x2="${{cx}}" y2="${{ly}}" stroke="#10212b" stroke-width="2"/><text x="${{cx}}" y="${{h-22}}" text-anchor="middle" class="axis-label">${{o.policy.replaceAll('_',' ')}}</text>`}});return x+'</svg>'}}
sel.addEventListener('change',redraw);redraw();
</script></main></body></html>'''
    path.write_text(html, encoding="utf-8")


def run_benchmark(output: str | Path, seeds: int = 5, duration: int = 420,
                  config: SimulationConfig | None = None) -> dict:
    if seeds < 2:
        raise ValueError("use at least two seeds to report variability")
    config = config or SimulationConfig()
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    (root / "traces").mkdir(exist_ok=True)
    runs = []
    for scenario in SCENARIOS:
        for seed in range(1, seeds + 1):
            trace = make_scenario(scenario, seed, duration)
            write_csv(root / "traces" / f"{scenario}-seed-{seed}.csv", trace)
            # Read back the written trace: reported runs consume the same CSV
            # artifact the user can inspect and replay.
            trace = read_csv(root / "traces" / f"{scenario}-seed-{seed}.csv")
            for policy in POLICIES:
                runs.append(simulate(policy, scenario, seed, trace, config))

    aggregate = _aggregate(runs)
    machine = "Machine details not captured"
    try:
        import platform
        machine = f"{platform.machine()} · {platform.processor() or 'Apple Silicon'} · {__import__('os').cpu_count()} logical CPUs"
    except Exception:
        pass
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("guardscale-%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": machine,
        "evidence_type": "synthetic_simulation",
        "seeds_per_scenario": seeds,
        "scenarios": list(SCENARIOS),
        "policies": list(POLICIES),
        "configuration": config.__dict__,
        "limitations": [
            "Synthetic traffic and classifier features; no real attack dataset labels used.",
            "Queue latency is an approximation, not measured application latency.",
            "Replica-seconds are a relative resource proxy; not cloud cost.",
            "One synthetic trace generator and fixed service capacity; no Kubernetes control-plane dynamics.",
        ],
        "runs": runs,
        "aggregate": aggregate,
    }
    (root / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (root / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [key for key, value in runs[0].items() if not isinstance(value, (dict, list))]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fields} for row in runs)
    write_site(root / "index.html", payload)
    return payload
