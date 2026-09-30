"""One FastAPI deployment serves both the API and the frontend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.gemini_service import ExtractionError, GeminiService
from app.models import NormalizeRequest, NormalizeResponse
from app.normalizer import normalize_clinic, normalize_procedure

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.gemini = GeminiService(
        api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
    )
    yield
    await application.state.gemini.close()


app = FastAPI(title="Gangnam Beauty Guide — Review Normalizer", version="1.0.0", lifespan=lifespan,
              description="Extract supported facts from multilingual treatment reviews and resolve clinic aliases locally.")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default errors echo the submitted input; reviews need not be reflected.
    return JSONResponse(status_code=422, content={"detail": "Submit a JSON object with a non-empty 'review' string of at most 10,000 characters."})


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.post("/api/normalize", response_model=NormalizeResponse, tags=["Reviews"])
async def normalize(payload: NormalizeRequest, request: Request):
    try:
        extraction = await request.app.state.gemini.extract(payload.review)
    except ExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    extraction.procedure_normalized = normalize_procedure(extraction.procedure_raw, extraction.procedure_normalized)
    return NormalizeResponse(extraction=extraction, normalization=normalize_clinic(extraction.clinic_raw))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
