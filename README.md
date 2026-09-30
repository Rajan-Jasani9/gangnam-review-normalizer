# Gangnam Beauty Guide — Review Normalizer

A small FastAPI demo that turns Korean or English cosmetic-treatment reviews into comparable English records. It translates and extracts supported facts, then resolves different clinic names against a local alias dataset. The first two **synthetic demo reviews** use `아이디병원` and `ID Plastic Surgery`; both resolve to **ID Hospital**.

## Architecture

`Vanilla HTML/CSS/JS → POST /api/normalize → Gemini + Pydantic validation → local RapidFuzz/alias normalization → human-readable result + JSON`

The LLM handles ambiguous unstructured-language extraction. Deterministic entity resolution handles canonical platform data. This prevents the model from freely inventing or renaming platform entities.

Clinic matching first uses Unicode-aware, case-insensitive exact aliases. Fuzzy matching uses full-string similarity, a **92% minimum**, an **8-point margin** over a competing clinic, and a minimum name length. Short, ambiguous, and unknown names remain unresolved and retain the extracted name. Confidence is string similarity, not a calibrated probability, proof of provider identity, or clinic quality. The eight clinic entries are demo alias data, not recommendations or verified listings.

Common procedures use a small exact alias dictionary; unlisted or multiple procedures retain the supported English extraction. Missing fields remain `null` or empty arrays. Raw clinic/procedure phrases must occur in the source. The model is instructed to ignore commands inside reviews, avoid invented facts, preserve uncertainty, and provide information extraction rather than medical advice. LLM output still requires review before downstream use.

## Local setup (Windows PowerShell, Python 3.12)

```powershell
cd D:\ganganam
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set your key in `.env` (never in source or frontend code):

```dotenv
GEMINI_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Existing environment variables take precedence over `.env`. Restart the server after changing configuration. Get a key from [Google AI Studio](https://aistudio.google.com/apikey). The model name is configurable so it can be changed if your account's model availability changes.

Run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open [the app](http://localhost:8000), [interactive API docs](http://localhost:8000/docs), or [health](http://localhost:8000/health). Alternatively, `.\.venv\Scripts\python.exe main.py` honors `PORT`, defaulting to `8000`.

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with your key, then:
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The app and API docs load without a key. Normalization returns a clear `503` until `GEMINI_API_KEY` is configured; no fabricated or offline extraction is substituted.

## API

```http
POST /api/normalize
Content-Type: application/json

{"review": "I had rhinoplasty at ID Plastic Surgery. I had swelling for two weeks."}
```

The response contains `extraction` and `normalization`, including the raw clinic, canonical name, matched alias, confidence, status (`matched`, `unresolved`, or `not_mentioned`), and match method (`exact` or `fuzzy`). The UI presents these as readable fields with collapsible JSON and a copy action.

Errors: invalid/empty/overlong input → `422`; provider quota → `429`; invalid model output or upstream failure → `502`; missing/invalid configuration → `503`; timeout → `504`. Inputs are limited to 10,000 characters, provider calls to 45 seconds, and errors do not expose provider bodies, credentials, or submitted reviews. No application database or review logging; review content is sent to Google Gemini for processing. Trust signals measure detail completeness, not verified safety.

## Render deployment

Push this project to a Git repository, then create a Render **Web Service** connected to it. Use a single deployment for both the frontend and API:

| Setting | Exact value |
| --- | --- |
| Language / runtime | `Python 3` |
| Root directory | Repository root (leave blank) |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| `PYTHON_VERSION` | `3.12.7` |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `GEMINI_API_KEY` | Your Gemini API key, entered as a Render secret |

Render supplies `PORT`; do not set it to `8000` there. Or use **New → Blueprint** with the included `render.yaml` and supply the unsynced API-key secret. `.env` and local virtual environments are gitignored. This repository is deployment-ready; a live Render service and a real Gemini request require your provider account and key. For a public demo, configure a Gemini project quota appropriate to the demo because the API intentionally has no authentication.

These commands match [Render's FastAPI deployment guide](https://render.com/docs/deploy-fastapi). Extraction uses the official [Google Gen AI Python SDK's Pydantic response-schema support](https://googleapis.github.io/python-genai/#pydantic-model-schema-support).

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover cross-language alias resolution, conservative fuzzy matching, unknown and ambiguous clinics, procedure normalization, full API response composition, missing fields, invalid requests, absent keys, malformed model responses, timeouts, and secret-safe provider failures. Provider calls in tests are mocked; these tests do not claim that live Gemini extraction has been verified.

After configuring the real key, submit the first two demo reviews in the browser or `/docs` and confirm both resolve to `ID Hospital`. Check the translated details against the source, including the absent surgeon and the reported recovery issues.
