# Local Kubernetes experiment

This is an isolated `kind` cluster backed by Docker Desktop. The workload is
reachable only on `127.0.0.1:8080`; the benchmark sends traffic only to that
local service. The input traffic is synthetic. CSV rows are real HTTP and
Kubernetes observations and are labeled `local_kubernetes_measurement`.

## Create the cluster and deploy the service

```sh
kind create cluster --config deploy/kind/cluster.yaml
docker build -t guardscale-demo:dev deploy/demo
kind load docker-image guardscale-demo:dev --name guardscale
kubectl apply -f deploy/demo/workload.yaml
kubectl rollout status deployment/guardscale-demo --timeout=120s
curl http://127.0.0.1:8080/healthz
```

The node containers should remain within the Docker Desktop VM resource budget.
The demo Deployment is capped at 500 millicores and 192 MiB per replica, with a
six-replica benchmark ceiling.

## Replay one trace

Install the package in editable mode or set `PYTHONPATH=src`, then run:

```sh
PYTHONPATH=src python3 -m guardscale.k8s_benchmark \
  --scenario legitimate_flash --policy guardscale --seed 1 \
  --duration 180 --out results/kubernetes/guardscale.csv
```

Available policies are `reactive`, `predictive`, and `guardscale`. The runner
replays a seeded synthetic trace, applies desired replica changes through
`kubectl`, and records requested/ready replicas, HTTP errors, and per-window
client latency. It writes a CSV and a JSON run summary. Run each policy against
the same scenario and seed for paired comparisons. This is an experimental
host-side controller prototype, not a production Kubernetes operator or a
validated security classifier.

## Remove the cluster

```sh
kind delete cluster --name guardscale
```
