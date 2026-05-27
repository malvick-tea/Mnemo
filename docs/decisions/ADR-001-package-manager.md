# ADR-001: Use `uv` as the Python package manager

- **Status:** accepted
- **Date:** 2026-02-01

## Context

Each Python service (`api`, `bot`, `workers`) needs reproducible dependency
resolution, a fast install path for CI, and ergonomic local development.
Candidates: `pip + venv`, `poetry`, `pdm`, `uv` (Astral), `hatch`.

## Decision

Use **`uv`** in all services. The Docker images use `uv pip install --system`
during build; locally developers run `uv run …`.

## Consequences

**Good:**
- Resolution is 10-100× faster than `poetry` (matters for cold CI cache).
- Lockfile format is portable across services; we can later add `uv workspace`
  if the services grow shared internal packages.
- Single binary, no `pip install poetry` chicken-and-egg.

**Trade-off:**
- `uv` is younger than `poetry`. We pin the toolchain version in `Makefile`
  and `Dockerfile`s; CONTRIBUTING.md tells humans which version we test.
- If `uv` ever takes a backwards-incompatible turn we live through one
  painful Friday — accepted.

## Alternatives considered

- **poetry** — battle-tested, but `poetry lock` on a cold cache for a
  ML-adjacent dep tree takes minutes; we'd feel it in CI on every PR.
- **pip-tools** — works, but `requirements.in` / `requirements.txt`
  pair is harder to read in PRs than a single lockfile.
- **pdm** — fine, but smaller community than `uv` and slower in our
  micro-benchmarks.
- **hatch** — focuses on packaging, dep management is a secondary concern.
