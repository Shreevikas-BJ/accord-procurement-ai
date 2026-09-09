import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .db import engine
from . import routes_auth, routes_catalog, routes_quotes, routes_decisions


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                **{k: getattr(record, k) for k in ("document_id", "stage", "mode", "error_type") if hasattr(record, k)},
            }
        )


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
app = FastAPI(
    title="Accord Procurement API",
    version="1.0.0",
    description="Local quote analysis with human review and deterministic decisions.",
)


@app.middleware("http")
async def csrf_and_headers(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-procurement-client") != "workspace":
        return JSONResponse(status_code=403, content={"detail": "Missing workspace request header."})
    origin = request.headers.get("origin")
    if origin and origin not in ("http://localhost:3000", "http://127.0.0.1:3000"):
        return JSONResponse(status_code=403, content={"detail": "Origin is not allowed."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, error):
    return JSONResponse(
        status_code=409, content={"detail": "This change conflicts with an existing record. Reload and try again."}
    )


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(routes_auth.router)
app.include_router(routes_quotes.router)
app.include_router(routes_decisions.router)
app.include_router(routes_catalog.router)
