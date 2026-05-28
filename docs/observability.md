# Observability

Mnemo speaks Prometheus. Bring your own scrape pipeline (Prometheus +
Grafana, Datadog, VictoriaMetrics, etc.) and point it at the targets
below.

## Targets

| Target              | URL                                  |
|---------------------|--------------------------------------|
| `api`               | `http://api:8000/metrics`            |
| `workers`           | `http://workers:9101/metrics`        |
| `dispatcher`        | `http://dispatcher:9101/metrics`     |
| `scheduler`         | `http://scheduler:9101/metrics`      |

The compose network keeps all of these on `mnemo_internal` — your
Prometheus container needs to join that network. The workers/dispatcher/
scheduler share a single port (different containers) so any one of them
will answer port 9101 on its own hostname.

## Example `prometheus.yml`

```yaml
scrape_configs:
  - job_name: mnemo
    metrics_path: /metrics
    static_configs:
      - targets: ['api:8000', 'workers:9101', 'dispatcher:9101', 'scheduler:9101']
```

## Metrics

All Mnemo-specific series share the `mnemo_` prefix. See
[ADR-005](decisions/ADR-005-observability.md) for the design.

### Capture

- `mnemo_capture_total{source_type, outcome}` — counter.
  `source_type` ∈ `{text,voice,photo,document,url,forward}`;
  `outcome` ∈ `{ok, rejected, error}`.
- `mnemo_capture_bytes_total{source_type}` — counter.
  Total ingested bytes per capture type.

### Query / RAG

- `mnemo_query_total{outcome}` — counter.
  `outcome` ∈ `{ok, empty, error}`.
- `mnemo_query_latency_seconds` — histogram. Buckets cover 100ms→60s.
- `mnemo_search_hits{retriever}` — histogram of result-set sizes.

### LLM

- `mnemo_llm_tokens_total{direction, provider}` — counter.
  `direction` ∈ `{prompt, completion}`; `provider` ∈ `{openrouter, ollama}`.
- `mnemo_llm_call_seconds{provider}` — histogram.
- `mnemo_llm_errors_total{provider}` — counter (retries exhausted).

### Workers

- `mnemo_worker_task_total{actor, outcome}` — counter.
  Recorded by a Dramatiq broker middleware → every actor is covered.
- `mnemo_worker_task_seconds{actor}` — histogram.
- `mnemo_queue_depth` — gauge. Length of `mnemo:tasks` Redis list,
  refreshed every ~5s by the dispatcher.

### Webhooks

- `mnemo_webhook_total{event, outcome}` — counter for n8n callbacks.
  `event` ∈ `{note-ready, note-failed}`;
  `outcome` ∈ `{accepted, duplicate, rejected, error}`.

## Dashboards

We don't ship a Grafana dashboard yet (skin to your taste). The panels
that have paid off in practice:

- **Capture mix** — stacked rate of `mnemo_capture_total` by source_type.
  Tells you what your bot is actually being used for.
- **RAG latency** — p50/p95/p99 over `mnemo_query_latency_seconds`.
  Anything >10s at p95 means LLM is the bottleneck.
- **Token spend** — `rate(mnemo_llm_tokens_total[1h])` ÷ provider price.
  Live cost meter; alert when it doubles.
- **Queue depth** — `mnemo_queue_depth` time-series.
  Should stay <100 in normal operation. Sustained growth = workers down
  or LLM provider is degraded.
- **Worker error rate** — `sum by (actor) (rate(mnemo_worker_task_total{outcome="error"}[5m]))`.
  Alert if any actor exceeds 5% errors over 15 minutes.

## Tracing (optional)

OpenTelemetry packages are in `mnemo_api`'s dependency tree but no
default tracer is configured. To enable:

```bash
MNEMO_OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4318
OTEL_SERVICE_NAME=mnemo-api
```

Wire your collector to wherever. We will not include Tempo/Jaeger in
the default compose stack — operators with tracing infra plug it in;
others ignore it.
