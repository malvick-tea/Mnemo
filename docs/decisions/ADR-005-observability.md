# ADR-005: Observability stack

**Status:** accepted · 2026-05-28

## Context

By Phase 5 Mnemo runs four long-lived Python services (api, workers,
dispatcher, scheduler) plus three datastores (Postgres, Qdrant, MinIO,
Redis). Without a metrics surface we can't answer the questions a
self-hosted operator actually asks ("is the queue stuck? how much am I
spending on the LLM? are voice notes timing out?") without tailing logs
by hand.

The mega-prompt called for "lightweight observability" — not a full
Datadog-style platform. We pick the smallest thing that lets a single
operator answer those questions from one Prometheus + one Grafana.

## Decision

**Prometheus is the metrics protocol.** Every service exposes a
text-format `/metrics` endpoint:

| Service     | Port | How served                                          |
|-------------|------|-----------------------------------------------------|
| `api`       | 8000 | FastAPI `make_asgi_app(REGISTRY)` mounted at `/metrics` |
| `workers`   | 9101 | `prometheus_client.start_http_server` (daemon thread) |
| `dispatcher`| 9101 | same as workers (different container, same port)    |
| `scheduler` | 9101 | same                                                |
| `webapp`    | 8080 | not instrumented (read-only, low traffic)           |

**One metrics module.** All counters/histograms live in
`services/api/src/mnemo_api/metrics.py`. The workers re-import them via
the shared `mnemo-api` package. Centralising the registry means label
cardinality is enforced in one place and `/metrics` output stays
predictable across services.

**What we instrument (v1):**

- **Capture:** `mnemo_capture_total{source_type, outcome}` and
  `mnemo_capture_bytes_total{source_type}` per endpoint.
- **Query/RAG:** `mnemo_query_total{outcome}` (ok/empty/error),
  `mnemo_query_latency_seconds` histogram, `mnemo_search_hits{retriever}`
  histogram.
- **LLM:** `mnemo_llm_tokens_total{direction, provider}` from
  provider-reported usage, `mnemo_llm_call_seconds{provider}` histogram,
  `mnemo_llm_errors_total{provider}`.
- **Workers:** `mnemo_worker_task_total{actor, outcome}` and
  `mnemo_worker_task_seconds{actor}` via a Dramatiq middleware
  (`MetricsMiddleware`) so future actors are covered automatically.
- **Queues:** `mnemo_queue_depth` gauge updated by the dispatcher on
  every poll cycle.
- **Webhooks:** `mnemo_webhook_total{event, outcome}` per inbound n8n
  callback.

**Tracing is opt-in.** OpenTelemetry deps are in `pyproject.toml` but
not wired into a default tracer. Operators set
`MNEMO_OTEL_ENABLED=true` + `OTEL_EXPORTER_OTLP_ENDPOINT=...` to plug
in their own collector. We don't ship Tempo/Jaeger in the compose file
— operators already running one will wire it up, others would just
ignore the extra container.

**Logs stay structlog JSON.** Stdout → docker logs → whatever the
operator pipes them to. Correlation IDs flow via context vars; every
log line includes `correlation_id`. No log shipper bundled in compose.

## Why this and not alternatives

- **vs. a full opinionated stack (Loki + Tempo + Grafana + Prom)**: too
  heavy for a self-hosted single-user product. We let the operator
  bring their own observability infra and just present standard
  protocols.
- **vs. statsd/StatsD-compatible exporters**: Prometheus pull is
  cheaper to operate (no push agent, no buffering). Single scrape
  target per service.
- **vs. instrumenting via OpenTelemetry metrics SDK**: more boilerplate
  per metric, and the OTEL Python SDK is still maturing. We can switch
  later because all metrics live in one module.

## Cardinality discipline

We label only by bounded enums (`source_type`, `outcome`, `provider`,
`actor name`). Never by user ID, note ID, or any free-text input. If a
new label would multiply series by a user-controlled value, it goes in
the log line, not in a metric.

## Consequences

- Operators get out-of-the-box Prometheus targets and a sensible set of
  panels (the `make seed-demo` panels in `docs/observability.md`).
- Adding a new actor or capture type is one new label value, not a new
  metric — chart panels keep working.
- We pay the cost of one extra HTTP listener per worker container
  (9101). Negligible RAM, no GC pressure.
- Tracing is the operator's problem, not ours, until v2 demands
  request-level latency breakdown.
