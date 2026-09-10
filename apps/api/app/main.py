import os
from fastapi import FastAPI, Request, HTTPException
from redis import Redis
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .db import engine
from .config import REDIS_URL
from .logging_config import configure_logging
from . import routes_auth, routes_catalog, routes_quotes, routes_decisions


configure_logging()
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
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        if os.getenv("REQUIRE_REDIS") == "true":
            Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2).ping()
    except Exception as error:
        raise HTTPException(503, "A required dependency is unavailable.") from error
    return {"status": "ok", "database": engine.dialect.name}


app.include_router(routes_auth.router)
app.include_router(routes_quotes.router)
app.include_router(routes_decisions.router)
app.include_router(routes_catalog.router)
