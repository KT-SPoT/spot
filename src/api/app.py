"""Factory: python -m uvicorn src.api.app:create_app --factory --workers 1."""
from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from src.api.jobs import JobError, JobRegistry
from src.api.models import ResearchRequest


def redact(value, secrets):
    """Keep keys out of returned warning strings, URLs and nested metadata."""
    if isinstance(value, dict):
        return {k: redact(v, secrets) for k, v in value.items()
                if not any(word in k.lower() for word in ("api_key", "certkey", "secret", "token", "password"))}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        if value.startswith(("https://", "http://")):
            try:
                parts = urlsplit(value)
                query = [(k, "[REDACTED]" if k.lower() in
                          {"key", "apikey", "api_key", "certkey", "token", "access_token", "secret"} else v)
                         for k, v in parse_qsl(parts.query, keep_blank_values=True)]
                value = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
            except ValueError:
                return "[INVALID_URL]"
        return value
    return value


def research_result(request, *, mode, progress=None):
    from src.integration_smoke import run_smoke
    from src.brief.renderer import render_markdown
    run = run_smoke(request, mode=mode, progress=progress)
    if not run["all_contracts_valid"]:
        raise ValueError("invalid Scout contract")
    state = run["state"]
    secrets = [v for k, v in os.environ.items() if v and len(v) >= 8 and
               any(word in k.upper() for word in ("KEY", "SECRET", "TOKEN", "CLIENT_ID", "PASSWORD"))]
    brief = redact(state["research_brief"], secrets)
    return {"mode": mode, "module_status": run["module_status"], "critic_is_mock": False,
            "critic_result": redact(state["critic_result"], secrets),
            "retry_history": state.get("retry_history", []),
            "research_brief": brief, "research_brief_markdown": redact(render_markdown(brief), secrets)}


def create_app(*, token=None, mode=None, runner=None):
    # Load only at explicit server startup, not on import or test discovery.
    if token is None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", encoding="utf-8-sig")
        token = os.environ.get("SPOT_API_TOKEN", "")
    mode = mode or os.environ.get("SPOT_API_MODE", "offline")
    if not isinstance(token, str) or len(token.strip()) < 24:
        raise RuntimeError("SPOT_API_TOKEN must be configured (at least 24 characters)")
    if mode not in ("offline", "live"):
        raise RuntimeError("SPOT_API_MODE must be offline or live")
    registry = JobRegistry(runner or (lambda request, progress: research_result(request, mode=mode, progress=progress)),
                           reports_progress=runner is None)

    @asynccontextmanager
    async def lifespan(app):
        yield
        registry.close()

    app = FastAPI(title="SPOT Research API", version="0.1", lifespan=lifespan)
    app.state.jobs = registry
    key_header = APIKeyHeader(name="X-SPOT-API-Key", auto_error=False)

    def authenticate(key=Depends(key_header)):
        if not isinstance(key, str) or not hmac.compare_digest(key.encode(), token.encode()):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_REQUEST",
            "fields": [{"field": ".".join(str(part) for part in e["loc"]), "type": e["type"]} for e in exc.errors()]}})

    @app.exception_handler(JobError)
    async def job_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code}},
                            headers={"Retry-After": "5"} if exc.status == 429 else None)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "spot-research"}

    @app.post("/v1/research/jobs", dependencies=[Depends(authenticate)])
    def submit(payload: ResearchRequest):
        job, created = registry.submit(payload.model_dump())
        return JSONResponse(status_code=202 if created else 200, content=job,
                            headers={"Location": job["status_path"], "Cache-Control": "no-store"})

    @app.get("/v1/research/jobs/{job_id}", dependencies=[Depends(authenticate)])
    def status(job_id: str):
        return JSONResponse(content=registry.get(job_id), headers={"Cache-Control": "no-store"})

    return app
