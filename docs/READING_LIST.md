# Reading list and annotation prompts

Read in this order. For each paper, annotate: problem/assumption; system signals and control action; workload and labels; baselines; measurement setup; limitations; what can be reproduced; and how it overlaps our claim.

1. **Jiang & Fard, “SPARK: Secure Predictive Autoscaling for Robust Kubernetes” (2026 preprint).** [arXiv](https://arxiv.org/abs/2603.26833) · [code](https://github.com/nyit-vancouver/SPARK). Closest claimed system. Check code and artifacts against paper; inspect use of HTTP 2xx share, Cilium/Hubble, external predictive dependency, and synthetic evaluation. Do not cite its claim as peer-reviewed without checking venue status.
2. **Qiu et al., “AWARE: Automate Workload Autoscaling with Reinforcement Learning in Production Cloud Systems,” USENIX ATC 2023.** [Paper](https://www.usenix.org/system/files/atc23-qiu-haoran.pdf). Production-readiness, safe exploration, workload adaptation, and evaluation discipline.
3. **Kubernetes Horizontal Pod Autoscaler documentation.** [Official docs](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/). Control-loop behavior, metric semantics, stabilization, readiness, and what an HPA baseline actually does.
4. **KEDA External Scalers documentation.** [Official docs](https://keda.sh/docs/latest/concepts/external-scalers/). Feasible integration interface and control-loop contract.
5. **Kelly et al., “Denial of wallet—Defining a looming threat to serverless computing” (2021).** [DOI](https://doi.org/10.1016/j.jisa.2021.102843) · [arXiv](https://arxiv.org/abs/2104.08031). Threat taxonomy and safe testbed rationale; note serverless billing differs from Kubernetes node/pod costs.
6. **Sharafaldin et al., “Developing Realistic Distributed Denial of Service (DDoS) Attack Dataset and Taxonomy” (2019).** [Official dataset page](https://www.unb.ca/cic/datasets/ddos-2019.html). Dataset construction, labels, traffic families, and limitations.
7. **Jiang et al., “A Meta Reinforcement Learning Approach for Predictive Autoscaling in the Cloud,” KDD 2022.** [DOI](https://doi.org/10.1145/3534678.3539063) · [arXiv](https://arxiv.org/abs/2205.15795). Predictive scaling baseline and model complexity trade-offs.
8. **AAPA, “An Archetype-Aware Predictive Autoscaler with Uncertainty Quantification for Serverless Workloads on Kubernetes” (2025 preprint).** [arXiv](https://arxiv.org/abs/2507.05653). Important overlap: uncertainty quantification already appears in predictive autoscaling; identify what differs in a DoW-aware objective and evaluation.
9. **SLO-Scaler, “Uncertainty-Aware SLO-Driven Autoscaling for Microservices” (2026 preprint).** [arXiv](https://arxiv.org/abs/2608.18390). Recent uncertainty-aware, SLO-driven scaling; compare its decision objective and threat model.
10. **SPARK follow-up search:** query recent proceedings and preprints for traffic-aware autoscaling, autoscaling attacks, flash-crowd/DDoS discrimination, and cost-aware admission. Maintain a related-work table before freezing novelty.

## Initial comparison questions for SPARK

- Is the repository runnable and does it contain the policy/model described in the paper?
- Does the offered workload include both successful malicious requests and legitimate requests that error under overload?
- Is 2xx/total a useful legitimacy signal when attacks can use valid endpoints and overload itself causes 5xx?
- Are reported comparisons paired across the same traces, and are uncertainty/repeated runs reported?
- What is actually open-source versus dependent on PredictKube or a cloud cluster?
- Which parts can our laptop reproduce, and what requires Linux/cloud resources?
