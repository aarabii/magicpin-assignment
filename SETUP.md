# Setup and Deployment Guide

## 1) Local Run

### Prerequisites

- Python 3.11+ (3.13 also works)
- pip

### Steps

1. Open terminal in this folder.
2. Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment:

```bash
copy .env.example .env
```

Add your values in `.env`:

```env
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=YOUR_GROQ_KEY
HOST=0.0.0.0
PORT=8080
DEBUG_LLM=false
```

4. Start server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

5. Health check:

```bash
curl http://127.0.0.1:8080/v1/healthz
```

## 2) Deploy (Generic PaaS)

Use the same repository folder as app root and set startup command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set env vars in platform secrets:

- `GROQ_API_KEY`
- `LLM_PROVIDER=groq`
- `LLM_MODEL=llama-3.3-70b-versatile`
- `DEBUG_LLM=false`

## 3) Required Endpoints

Ensure these are reachable publicly:

- `GET /v1/healthz`
- `GET /v1/metadata`
- `POST /v1/context`
- `POST /v1/tick`
- `POST /v1/reply`

## 4) Pre-Submission Checklist

- Bot URL is public and stable.
- All endpoints respond within timeout budget.
- `.env` is not committed.
- No API key strings exist in tracked files.
- `/v1/metadata` has correct team details.
