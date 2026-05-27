# n8n workflows — authoring guide

n8n is a first-class citizen in Mnemo: branchy / fallback-heavy pipelines
live there so users can fork and edit them without touching Python.

## Conventions every workflow must follow

### 1. Trigger

A Webhook node at `/webhook/mnemo/<slug>`. The Mnemo Core API posts a JSON
body with at minimum `{ "note_id": "..." }`.

### 2. Auth (HMAC signature)

The **first node after the trigger** is a Function node named
`verify_hmac`. It computes `HMAC-SHA256(secret, "${ts}.${body}")` and
compares to the `X-Mnemo-Signature` header. Reject if:

- header missing
- timestamp older than 5 minutes (`abs(now - ts) > 300`)
- HMAC mismatch

Secret is the `MNEMO_WEBHOOK_HMAC_SECRET` env var passed into the n8n
container at compose-up time.

### 3. Idempotency

Every webhook carries an `Idempotency-Key` header. The workflow should use
n8n Static Data to record `key → response`; on a repeat we return the
cached response and skip the work.

### 4. Retries

Every HTTP Request node has Retry On Fail enabled, 3 attempts, 1500 ms
between tries. The default `expectedResponse` is `2xx`.

### 5. Callback

On success: POST to `${MNEMO_API_BASE_URL}/v1/webhooks/n8n/note-ready`
with the same HMAC signing.
On failure (after retries exhausted): POST to `note-failed`.

Both callbacks must include the `Idempotency-Key` header derived from
`<workflow-slug>:<note_id>:<truncated-timestamp>`.

### 6. Sticky note

The first node in the canvas is a Sticky Note with:

- one-line purpose
- trigger source (which Mnemo capture type fires it)
- expected input shape (JSON keys)
- known failure modes and how the workflow recovers

This is what a contributor reads first when forking your workflow.

### 7. Function vs Code node

- Prefer **HTTP Request + native nodes** over Function nodes for legibility.
- When you must use a Function node, set `runOnceForEachItem` deliberately
  and document why in a Sticky Note.

## Local development loop

```bash
make n8n-up                 # starts n8n + deps; UI on http://localhost:5678
# log in with N8N_BASIC_AUTH_USER / N8N_BASIC_AUTH_PASSWORD from .env
```

Inside n8n:

1. Import the workflow you want to edit from `Workflows → Import from File`.
2. Edit in the UI.
3. Click `Workflow → Download` to export the new JSON.
4. Replace `n8n/workflows/<id>-<name>.json` in your worktree.
5. Open a PR. CI re-imports workflows in a fresh n8n container to verify the
   JSON is well-formed.

## Testing a workflow

```bash
# In a separate shell:
curl -X POST http://localhost:5678/webhook/mnemo/001-url-ingest \
  -H 'Content-Type: application/json' \
  -H "X-Mnemo-Timestamp: $(date +%s)" \
  -H "X-Mnemo-Signature: $(./scripts/hmac_sign.sh body.json)" \
  -H "Idempotency-Key: dev-$(date +%s)" \
  -d @body.json
```

The bundled `scripts/hmac_sign.sh` mirrors the Python signing code; useful
for testing without bringing the bot up.

## Adding a brand-new workflow

1. Pick a 3-digit slug (`009-...`) and a kebab-case name.
2. Copy `001-url-ingest.json` as a starting template; rename the trigger
   path; update the Sticky Note.
3. Add an entry to this file.
4. Update `n8n/credentials.example.json` if it needs new credentials.

## Why n8n?

We move heavy/branchy pipelines to n8n so users can rewire them without
forking Python code. The Dramatiq worker tier owns hot-path work (text
embedding, short summaries). Read ADR-003 for the full rationale.
