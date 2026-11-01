# Workload and security data sources

No single public dataset provides ground-truth labels for “legitimate popularity spike versus denial-of-wallet traffic” together with Kubernetes replica, latency, and cost outcomes. The benchmark therefore needs multiple sources plus controlled, labeled replay. A trace is evidence for only the fields it actually contains.

| Source | What it offers | How GuardScale can use it | Main limitation |
| --- | --- | --- | --- |
| [Alibaba Cluster Trace v2018](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018) | Production cluster workload/resource traces, about 4,000 machines over 8 days according to the maintainers | Workload intensity/variability replay after a documented mapping to request arrivals or resource demand | Not HTTP requests, no benign/attack labels, no per-service web latency. Mapping is a model assumption, not ground truth. |
| [Google Cluster Workload Traces 2019](https://github.com/google/cluster-data/blob/master/ClusterData2019.md) | Production resource traces for eight Borg cells over May 2019, about 2.4 TiB compressed and accessed through BigQuery per maintainers | Independent resource/workload pattern only if a small query/sample can be used without downloading the full trace | Not practical as a local raw download; no end-user/access patterns or attack labels. It is not an HTTP request trace. |
| [CIC-DDoS2019](https://www.unb.ca/cic/datasets/ddos-2019.html) | PCAPs and flow CSVs with benign background and labeled attack periods/families | Offline detector feature sanity checks and attack-family coverage; cite the dataset paper | 2019 testbed traffic, limited benign users, and flow-level features; not a cloud autoscaling benchmark or realistic flash-crowd set. Do not equate dataset accuracy with deployment performance. |
| [CICIoT2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html) | Labeled benign and attack traffic for IoT devices | Optional out-of-domain stress test for detection features | IoT traffic does not represent web service requests or Kubernetes scale economics. |
| Controlled workload generation | Seeded legitimate browsing/session mixes, flash crowds, bursty background, low-and-slow and high-rate attack patterns | Primary end-to-end dataset for matched policy evaluation; preserve exact ground-truth class and offered load | Synthetic assumptions can bias results. Publish generator, parameters, seeds, and realistic ranges; never call it production traffic. |

## Recommended use

1. Start with controlled application-level request scenarios because they can carry labels and be replayed through the same service.
2. Add CIC-DDoS2019 for offline network/flow-feature exploration only if its formats match selected features; do not funnel its labels into Kubernetes scaling claims.
3. Add Alibaba/Google traces for workload-shape robustness only, with transformations documented and sensitivity-tested.
4. Keep train, validation, and test partitions separated by time and by full scenario/attack profile. Randomly splitting adjacent flows/windows risks leakage.
5. Record source URL, access date, version/checksum, license/citation, transformations, filtering, and label mapping in `data/manifest.yaml` before downloading.

## Download policy

Keep raw data outside Git (the repository has a `data/` placeholder). Do not silently mirror multi-gigabyte PCAPs. The official CIC page permits redistribution subject to required citation; still prefer a reproducible download script and a separate checksum manifest. Check each source's current license and terms at download time.
