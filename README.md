# 🔍 GitHub Profile Reviewer

A small full-stack tool that takes a **GitHub username (or profile URL)**, fetches the
user's public repositories, reads each project's README, and uses **Claude (Anthropic)**
to assess every project — its complexity, how clear the README is, and the level of
experience it reflects. Results are shown as readable cards in a web UI.

![level badges: Basic / Intermediate / Advanced](https://img.shields.io/badge/levels-Basic%20%7C%20Intermediate%20%7C%20Advanced-blue)

---

## What it does

1. Accepts a username or full profile URL (`torvalds` or `https://github.com/torvalds`).
2. Fetches the user's public repos via the GitHub REST API (most-recently-pushed first).
3. Reads each repo's README (raw file endpoint).
4. Sends repo metadata + README to Claude with one focused prompt → gets back a small
   JSON verdict: `level`, `readme_clarity`, `assessment`.
5. Displays a short, colour-coded summary per project.

---

## Tech stack & why

The role is **Python-first full-stack**, so the stack mirrors that directly:

| Layer    | Choice                         | Why |
|----------|--------------------------------|-----|
| Backend  | **Python + FastAPI**           | Core language for the role; FastAPI gives typed, async REST endpoints with almost no boilerplate. |
| AI       | **Claude (Anthropic) — Haiku** | Fast and cheap; the team works with Claude Code daily. One focused prompt returns strict JSON. |
| Frontend | **React + TypeScript (Vite)**  | Shows the front end of "full-stack"; TypeScript keeps the API contract typed end-to-end. |
| Tests    | **pytest + respx**             | GitHub calls are mocked and the AI call is stubbed, so tests run offline and for free. |
| CI       | **GitHub Actions**             | Runs backend tests + frontend type-check/build on every push. |

I deliberately kept it small: **one backend endpoint, one page.** No database — the task
is read-only and per-request, so persistence would be overengineering.

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app + /api/review endpoint
│   │   ├── github_client.py  # GitHub API calls + username/URL parsing
│   │   ├── ai.py             # Claude assessment (focused prompt → JSON)
│   │   └── models.py         # Pydantic request/response models
│   ├── tests/                # pytest suite (GitHub mocked, AI stubbed)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/                  # React + TS UI (App.tsx, types.ts, index.css)
└── .github/workflows/ci.yml
```

---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+** (tested on 22)
- An **Anthropic API key** → https://console.anthropic.com (Haiku usage for a profile
  costs a fraction of a cent).

---

## Setup & running

You need **two terminals** — one for the backend, one for the frontend.

### 1. Backend (FastAPI)

```bash
cd backend

# Create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Configure your API key
cp .env.example .env        # Windows: copy .env.example .env
# then edit .env and paste your ANTHROPIC_API_KEY

# Run the API (http://localhost:8000)
uvicorn app.main:app --reload
```

Interactive API docs are available at http://localhost:8000/docs.

### 2. Frontend (React)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Open **http://localhost:5173**, type a GitHub username, and hit **Review**.
(The Vite dev server proxies `/api` to the backend automatically.)

---

## Using the API directly (no frontend)

```bash
curl "http://localhost:8000/api/review?username=torvalds&limit=5"
```

`limit` (1–30, default 10) caps how many repos are reviewed so large profiles stay fast
and cheap.

---

## How AI is used

- **One focused prompt per repo** (`backend/app/ai.py`). The system prompt asks Claude
  to act as a senior reviewer and return **only** a JSON object with three fields.
- The assistant turn is **prefilled with `{`** to reliably get clean JSON back.
- The README is **truncated to ~6k chars** to keep token cost and latency low.
- Every AI call is wrapped so a failure or malformed reply **degrades gracefully** to a
  fallback verdict instead of crashing the whole review.

## Error handling

- **Nonexistent profile** → `404` with a clear message.
- **Repo with no README** → still listed, marked `README: Missing`, assessed from
  metadata (never crashes).
- **GitHub rate limit** → `502` with a hint to set a `GITHUB_TOKEN`.
- **Missing `ANTHROPIC_API_KEY`** → `500` telling you exactly what to fix.

An optional `GITHUB_TOKEN` (in `.env`) raises GitHub's rate limit from 60 → 5000 req/hr.

---

## Tests & CI

```bash
cd backend
pytest -q          # 15 tests, all mocked — no network or API key needed
```

GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests and the frontend
type-check/build on every push.

---

## How this meets the brief

**GitHub public API, token optional.** Repos are fetched from the public
`GET /users/{username}/repos` endpoint with **no token required**
(`backend/app/github_client.py` → `fetch_repos`). A `GITHUB_TOKEN` is purely
optional and only raises the rate limit (60 → 5000 req/hr); a clear `502`
points you to set one if you hit the limit unauthenticated.

**READMEs via the raw file endpoint.** Each README is pulled in a single call
from `GET /repos/{owner}/{repo}/readme` using the `application/vnd.github.raw`
media type (`fetch_readme`). A missing README returns `None` and the repo is
still assessed from its metadata — never a crash.

**Smart use of AI — *when* and *how*, not just running it:**

| Decision | Where | Why |
|----------|-------|-----|
| **Haiku, not a bigger model** | `ai.py` (`MODEL`) | Fast + cheap, and plenty for judging a README — right tool for the job. |
| **One focused prompt → strict JSON** | `ai.py` (`SYSTEM_PROMPT`) | Returns exactly 3 fields (`level`, `readme_clarity`, `assessment`), 1–3 sentences — concise and predictable. |
| **Assistant prefill of `{`** | `ai.py` (`assess_repo`) | Forces clean JSON instead of chatty prose the frontend can't parse. |
| **README capped at ~6k chars** | `ai.py` (`MAX_README_CHARS`) | Keeps token cost/latency low; large READMEs add noise, not signal. |
| **Graceful fallback, never raises** | `ai.py` (`_fallback`) | One unreliable AI response can't crash the whole review. |
| **Repos reviewed in parallel** | `app/main.py` (`asyncio.gather`) | Many repos assessed at once, not one-by-one. |
| **AI stubbed in tests** | `backend/tests/` | Tests run offline and free — no AI calls in CI. |

---

## Notes on the approach

- **AI tools used:** built with **Claude Code**, which matches how the team works.
- **Approach:** start from the role's stack (Python/FastAPI + React/TS), keep the scope
  to the smallest thing that genuinely works end-to-end, and lean on tests + CI as cheap
  signals of quality rather than adding architecture the task doesn't need.
- **Main challenge:** getting **reliable, structured output** from the LLM. Solved with a
  strict "JSON-only" system prompt, an assistant prefill of `{`, and a graceful fallback
  so one odd response can't break the run.
