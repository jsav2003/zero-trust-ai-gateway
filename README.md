# Zero Trust AI Gateway

A prompt scanning service: it analyzes a prompt for PII and risk, redacts it when needed, and writes an audit record. It is the scan component of a zero-trust LLM setup — it does not proxy traffic to a downstream model, and it is not a drop-in replacement for one.

Built with FastAPI, LangGraph and Gemini 3.6 Flash.

![Demo](docs/demo.gif)

---

## What it does

`POST /v1/security/scan` runs a two-node LangGraph over the incoming prompt:

1. **Analyzer** — one Gemini call with structured output, returning `risk_score` (0–10) and `pii_detected` (bool).
2. **Router** — a pure function, no external calls:

   ```python
   if state["pii_detected"] or state["risk_score"] > 5.0:
       return "sanitizer_node"
   return END
   ```

3. **Sanitizer** — a second Gemini call that replaces sensitive spans with `[REDACTED]`. Only runs when the router sends it there.

The response is returned immediately; the audit record is written to PostgreSQL in a background task.

**Cost per request:** one Gemini call for a clean prompt, two when redaction is triggered.

## Quickstart

Requires Python 3.12 and Docker.

```bash
git clone https://github.com/jsav2003/zero-trust-ai-gateway.git
cd zero-trust-ai-gateway

cp .env.example .env        # fill in GOOGLE_API_KEY and GATEWAY_API_KEY
docker compose up -d db     # PostgreSQL on :5432
alembic upgrade head

pip install -e ".[dev]"
uvicorn app.main:app --env-file .env --reload
```

Then:

```bash
curl -X POST localhost:8000/v1/security/scan \
  -H 'X-API-Key: <your-gateway-key>' \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u1","original_prompt":"my ID is 1144012345 and I live in Cali"}'
```

Interactive docs at `/docs`.

## API

| Method | Path | Auth |
|---|---|---|
| `POST` | `/v1/security/scan` | `X-API-Key` |
| `GET` | `/health` | none |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | none |

That's the whole surface. There is no endpoint to read the audit log back — records are queried directly in SQL.

Authentication is a single shared secret compared with `secrets.compare_digest`. If `GATEWAY_API_KEY` is unset the scan endpoint returns `503` rather than accepting every caller — an unset key would otherwise make the comparison succeed against an empty header.

## Configuration

| Variable | Default | If missing |
|---|---|---|
| `GOOGLE_API_KEY` | `""` | graph fails on the first request, not at startup |
| `GATEWAY_API_KEY` | `""` | `/v1/security/scan` returns `503` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/gateway_db` | uses default |
| `CORS_ALLOW_ORIGINS` | `http://localhost:8000` | uses default |

The Gemini client is built lazily and cached, so importing the app requires no credentials — the module imports cleanly in a bare container.

## Tests

```bash
pytest -v
```

Six cases, no network, no database, no API key required. They cover the routing rule (including the `5.0` boundary, which does *not* route to the sanitizer) and the persistence path with the graph stubbed.

The endpoint test exists for a specific reason. `pii_detected` was being read from a state key that never existed, so it silently persisted as `false` on every record — including the ones the analyzer had flagged and the sanitizer had redacted. The bug survived because nothing covered it. The test was verified by reintroducing the broken expression and confirming it fails.

## Known limitations

These are properties of the current implementation, not a roadmap.

- **The audit write is best-effort.** The client gets `200` before the `INSERT` completes. If it fails, the exception is logged to stdout and never retried, and the caller has no way to know the record was lost.
- **`original_prompt` is stored in plaintext**, including the spans the analyzer flagged as PII. No column-level encryption, no retention policy.
- **`sanitized_prompt` equals `original_prompt` when nothing was redacted.** The initial state seeds it with the original, and the sanitizer never runs on a clean prompt. Identical values mean *not sanitized*, not *sanitized and unchanged*.
- **A `risk_score` outside 0–10 loses the record entirely.** The analyzer's output is unbounded, the response model is not. If Gemini returns `10.5`, response validation raises, the client gets `500`, and the background task never runs — so no audit row is written either.
- **`user_id` is supplied by the caller and never verified.** The gateway authenticates the calling *service*, not the end user. Anyone holding the key can write records attributed to any `user_id`.
- **Detection depends on the model's judgment**, not on deterministic rules. There is no regex fallback, no allowlist, and no validation that the sanitizer returned only the sanitized text.
- **No rate limiting**, no key rotation, no timeouts or retries on the Gemini calls.
- **`/health` is a static response.** It does not check PostgreSQL or the Gemini API, so a `200` says the process is up and nothing more.

`docs/estado-real.md` is the full inventory of what the code does and doesn't do, verified against the source rather than against this file.

## Not implemented

Named explicitly because the architecture implies them: downstream LLM proxying, an audit-log read API, LangSmith instrumentation, pgvector embeddings, an application Dockerfile, and CI.

## License

MIT
