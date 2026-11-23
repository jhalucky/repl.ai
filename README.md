# inbox-guard

Email reply tracker for founders and managers. Connects a Gmail inbox, decides which
threads need a reply and how urgent they are, tracks unanswered threads, and alerts
on Telegram.

This is the working name; the Python package is `app`.

## Prerequisites

- Python 3.12
- Docker with Compose
- A virtualenv is recommended

Postgres is published on host port **5434** so it does not collide with other
local Postgres instances. Inside the container the server still listens on 5432.

## Setup

```bash
cp .env.example .env
docker compose up -d
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

Generate a Fernet key for `TOKEN_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Run the API

```bash
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health` → `{"status":"ok"}` (requires Postgres).

Open the founder UI: `http://localhost:8001/` (or 8000). Click **Connect a Gmail account**
for each mailbox after completing the Google Cloud setup below.

## Connect Gmail

Read-only access (`gmail.readonly`). The app never sends, deletes, or modifies mail.
Refresh tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY`.

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. **APIs & Services → Library** → enable **Gmail API**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - Add an app name and support email
   - Scopes: `https://www.googleapis.com/auth/gmail.readonly`, `openid`, `email`
   - **Test users**: add the Google account you will connect (required while the app is in Testing)
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URI: `http://localhost:8000/auth/google/callback`
     (must match `GOOGLE_REDIRECT_URI`)
5. Copy the client ID and secret into `.env`:

```bash
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

6. Run migrations if you have not: `alembic upgrade head`
7. Start the API: `uvicorn app.main:app --reload`
8. In a browser, open `http://localhost:8000/auth/google/start`, sign in as a test user, and accept.
9. List recent threads (no bodies printed):

```bash
python -m app.gmail.cli threads --limit 20
```

If Google returns `invalid_grant` (token expired or revoked), the account is marked
`needs_reconnect`. Visit `/auth/google/start` again.

## Sync Gmail into the database

While the API is running, a daily job (default 09:00 `DEFAULT_TIMEZONE`) syncs every
connected Gmail account and emails a classified report to `FOUNDER_ALERT_EMAIL`.
Set `ENABLE_SCHEDULER=false` to disable it.

```bash
python -m app.jobs.sync_job
python -m app.jobs.digest_job
python -m app.jobs.digest_job --skip-sync
```

New or changed threads are classified. A thread becomes `answered` when the last
message is from you. Running the job twice does not create duplicate threads or
classifications.

The founder report lists inbound threads that **need a reply** and those that **do not**.
A thread **needs attention** when it is `open`, `needs_reply` is true, the last
message is not from you, and it has waited at least the urgency threshold
(5: 1h, 4: 2h, 3: 24h, 2: 48h, 1: never).

## Classifier CLI

Classify a JSON list of `{from, subject, body, headers, label?}` objects. Provider
settings come from the environment only. Email bodies are never printed.

```bash
python -m app.pipeline.classifier tests/fixtures/sample_emails.json
python -m app.pipeline.classifier emails.json --limit 20
```

`LLM_MODEL` is required. Tests use a fake provider and do not need an API key.

## Pointing the LLM at a provider

Set `LLM_PROVIDER`, `LLM_KEY`, `LLM_MODEL`, and (for OpenAI-compatible APIs)
`LLM_BASE_URL`. Optional: `LLM_JSON_MODE`, `LLM_DISABLE_THINKING`,
`LLM_MAX_TOKENS`, `LLM_TIMEOUT_S`, `LLM_PRICE_INPUT_PER_M`,
`LLM_PRICE_OUTPUT_PER_M`.

| Service    | `LLM_PROVIDER`       | `LLM_BASE_URL`                                              | Notes |
|------------|----------------------|---------------------------------------------------------------|--------|
| OpenAI     | `openai_compatible`  | `https://api.openai.com/v1`                                   | Default base URL |
| Groq       | `openai_compatible`  | `https://api.groq.com/openai/v1`                              | |
| OpenRouter | `openai_compatible`  | `https://openrouter.ai/api/v1`                                | |
| Gemini     | `openai_compatible`  | `https://generativelanguage.googleapis.com/v1beta/openai/`    | |
| Ollama     | `openai_compatible`  | `http://localhost:11434/v1`                                   | `LLM_KEY` can be any string or empty |
| Anthropic  | `anthropic`          | unused                                                        | Native Messages API; `LLM_BASE_URL` is ignored |

Examples:

```bash
# OpenAI
LLM_PROVIDER=openai_compatible
LLM_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1

# Groq
LLM_PROVIDER=openai_compatible
LLM_KEY=gsk_...
LLM_MODEL=llama-3.1-8b-instant
LLM_BASE_URL=https://api.groq.com/openai/v1

# OpenRouter
LLM_PROVIDER=openai_compatible
LLM_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o-mini
LLM_BASE_URL=https://openrouter.ai/api/v1

# Gemini (OpenAI-compatible endpoint)
LLM_PROVIDER=openai_compatible
LLM_KEY=...
LLM_MODEL=gemini-2.0-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# Ollama (local; no real key required)
LLM_PROVIDER=openai_compatible
LLM_KEY=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434/v1
LLM_JSON_MODE=false

# Anthropic
LLM_PROVIDER=anthropic
LLM_KEY=sk-ant-...
LLM_MODEL=claude-haiku-4-5
```

Set `LLM_JSON_MODE=false` if the provider rejects `response_format={"type":"json_object"}`.

## Using a local model (Ollama / LM Studio / llama.cpp)

Any server that speaks the OpenAI chat completions API works. Example for Qwen3
on Ollama (thinking models need extra time and `/no_think`):

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_KEY=ollama
LLM_MODEL=qwen3:8b
LLM_DISABLE_THINKING=true
LLM_JSON_MODE=false
LLM_MAX_TOKENS=300
LLM_TIMEOUT_S=120
```

LM Studio is typically `http://localhost:1234/v1`. llama.cpp's OpenAI-compatible
server is typically `http://localhost:8080/v1`. `LLM_KEY` can be any string.

Troubleshooting:

- **Timeouts** — local reasoning models are slow. Raise `LLM_TIMEOUT_S` (120–180 is common for Qwen3 8B).
- **Empty or non-JSON output** — set `LLM_JSON_MODE=false` (many local servers reject `response_format`). The parser still extracts a JSON object from the reply.
- **Truncated context** — email bodies are already capped at 2,000 characters. If the JSON itself is cut off, raise `LLM_MAX_TOKENS`.
- **Thinking text in output** — Qwen3 may wrap reasoning in `<think>...</think>` (or leave `<think>` unclosed). `LLM_DISABLE_THINKING=true` appends `/no_think` to the user message; the parser also strips think blocks before JSON extraction.

## Tests and lint

Tests use a separate `inboxguard_test` database (created by `docker/init-db.sql`).
Postgres must be running. Classifier tests do not call the network.

```bash
docker compose up -d
pytest
ruff check .
```

Optional type check:

```bash
mypy
```

## Project layout (current)

```
app/
  main.py          FastAPI app, founder UI, /health, scheduler startup
  web/             connect-Gmail page
  config.py        settings from env
  db/              SQLAlchemy models, session, Alembic migrations
  providers/       LLMProvider protocol, OpenAI-compatible + Anthropic
  pipeline/        rules filter, body cleaning, scoring, classifier, thread state
  gmail/           OAuth, encrypted tokens, read-only client, threads CLI
  alerts/          founder digest email
  jobs/            daily sync + digest
tests/
  fixtures/sample_emails.json
docker-compose.yml
.env.example
```
