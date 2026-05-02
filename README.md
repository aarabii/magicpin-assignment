# Magicpin Assignment - Vera Bot

Production-ready FastAPI bot for the Magicpin AI Challenge.

This package is prepared for direct GitHub hosting/deployment and contains only required runtime files (no API keys or local debug artifacts).

## What Is Included

- `bot/` - bot logic and API handlers
- `dataset/` - category and seed context files
- `expanded/` - expanded deterministic context files
- `main.py` - ASGI entrypoint (`app`)
- `requirements.txt` - Python dependencies
- `Procfile` - process command for common PaaS hosting
- `.env.example` - environment variable template
- `SETUP.md` - local and cloud deployment instructions

## API Contract Implemented

- `GET /v1/healthz`
- `GET /v1/metadata`
- `POST /v1/context`
- `POST /v1/tick`
- `POST /v1/reply`

## Quick Start

1. Create virtual env and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Create `.env` from template and add your API key:

```bash
copy .env.example .env
```

3. Run server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

4. Verify:

```bash
curl http://127.0.0.1:8080/v1/healthz
```

## Required Environment Variables

- `LLM_PROVIDER` (default: `groq`)
- `LLM_MODEL` (default: `llama-3.3-70b-versatile`)
- `GROQ_API_KEY` (required for Groq)
- `PORT` (default: `8080`)
- `HOST` (default: `0.0.0.0`)
- `DEBUG_LLM` (`true`/`false`)

## Notes

- Do not commit `.env`.
- Keep API keys in deployment platform secret settings.
- Dataset is pre-bundled to allow immediate startup.
