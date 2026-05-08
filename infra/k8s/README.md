# Kubernetes Manifests

Plain manifests + a Kustomize entrypoint. No Helm — keep diffs reviewable.

## Layout

| File | Purpose |
|---|---|
| `namespace.yaml` | `guardian-stream` namespace |
| `agent-configmap.yaml` | Non-secret env (Kafka bootstrap, topic names, model id, top-k) |
| `agent-secret.yaml` | **Template only.** Replace `REPLACE_ME` or wire to External Secrets / Vault before applying |
| `agent-deployment.yaml` | Python LangGraph agent + PVC for the Chroma SEC index |
| `agent-service.yaml` | ClusterIP for `/health` and `/ready` |
| `gateway-deployment.yaml` | Java Spring Boot gateway + ClusterIP service |
| `keda-scaledobject.yaml` | KEDA `ScaledObject` — autoscales the agent on Kafka consumer lag for `sanitized-prompts` (lag threshold 20, min 1, max 10) |
| `kustomization.yaml` | Apply everything in one go |

## Apply

```bash
# Create the API key secret out-of-band (never commit it):
kubectl -n guardian-stream create secret generic guardian-stream-agent-secrets \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Then the rest:
kubectl apply -k infra/k8s/
```

## Prerequisites

- Kafka deployed in the same namespace at `kafka.guardian-stream.svc.cluster.local:9092` (Strimzi or equivalent)
- KEDA installed cluster-wide (https://keda.sh)
- A `StorageClass` that satisfies `ReadWriteOnce` for the SEC index PVC
- Container images built and pushed to a registry the cluster can pull from

## Scaling Behavior

The agent autoscales on Kafka consumer lag, not CPU. Rationale: prompt synthesis is bound by upstream LLM latency, not local compute, so the right load signal is "how many sanitized prompts are queued?" The `lagThreshold: 20` means each replica targets ~20 in-flight prompts; KEDA spins up additional replicas when the average exceeds that.

`fallback` keeps 2 replicas alive if the Kafka scaler fails health checks 3× in a row, so a Kafka outage doesn't scale the deployment to zero.
