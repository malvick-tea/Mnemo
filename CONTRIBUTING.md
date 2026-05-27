# Contributing to Mnemo

Thanks for your interest. Mnemo is small, opinionated, and built for the
self-hoster crowd; we try to keep the PR loop fast.

## Before you open a PR

1. **Open an issue first** for anything bigger than a typo fix or trivial bug.
   Two hours of back-and-forth on an issue is cheaper than two weeks of
   back-and-forth on a PR.
2. **Read `ARCHITECTURE.md`** so we share vocabulary.
3. **Check `PLAN.md`** — if it's already on the roadmap, say so in the issue.

## Setup

```bash
# Toolchain
curl -LsSf https://astral.sh/uv/install.sh | sh

# Repo
git clone https://github.com/yourname/mnemo.git
cd mnemo
make dev    # starts the dev compose stack (hot reload, exposed ports)
```

## Code style

- **Typing.** `mypy --strict` must pass. `Any` only with a comment explaining
  why no other type works.
- **Lint/format.** `ruff check` and `ruff format --check` clean. Pre-commit
  enforces this.
- **Async.** Never block the event loop. `asyncio.to_thread` for unavoidable
  sync calls. No `time.sleep` in async code paths.
- **Errors.** Custom exception hierarchy in `mnemo_api.exceptions`. No bare
  `except`. External HTTP gets timeouts + retries.
- **Logging.** `structlog`, JSON, one line per request. No `print`. Don't log
  secrets or message bodies unless `MNEMO_LOG_PII=true`.
- **Comments.** Explain *why*, not *what*. The code already says what.

## Tests

```bash
make test          # all
make test-unit
make test-int      # spins up real Postgres / Qdrant / Redis via testcontainers
make eval          # RAG eval suite (50 Q&A pairs)
```

Target coverage on business logic: ≥ 70%. Critical flows (capture, hybrid
search, RAG) get integration tests against real services.

## Commit & PR

- [Conventional Commits](https://www.conventionalcommits.org/). `feat:`, `fix:`,
  `chore:`, `docs:`, etc.
- Squash-merge by default. PR title is what lands on `main`.
- PR description: motivation, what changed, screenshots / log snippets where
  useful.
- CI must be green. We don't merge red.

## n8n workflows

Workflows live in `n8n/workflows/*.json`. To edit one:

1. `make n8n-up` (exposes n8n at `http://localhost:5678`).
2. Edit visually in the n8n UI.
3. Export the workflow (n8n UI → menu → Download).
4. Replace `n8n/workflows/<id>-<name>.json`.
5. Commit. A reviewer will sanity-check via the diff.

See `docs/n8n-workflows.md` for the conventions every workflow must follow
(HMAC validation, idempotency, retry policy, etc.).

## Architecture Decision Records (ADRs)

If you're making a non-obvious design choice, drop an ADR in
`docs/decisions/`. Template at `docs/decisions/_template.md`. We'd rather have
a 10-line ADR than re-litigate the same decision six months later.

## Security

Found a vulnerability? Don't open a public issue. Email the address in
[SECURITY.md](SECURITY.md).

## Code of conduct

Be kind. We're all just trying to ship.
