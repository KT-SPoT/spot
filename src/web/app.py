"""Loopback-only MVP: uvicorn src.web.app:create_app --factory --host 127.0.0.1 --port 8768."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError

from src.api.app import redact
from src.api.models import ResearchRequest
from src.web import places

STATIC = Path(__file__).parent / 'static'
COOKIE = 'spot_session'


def create_app(*, token=None, n8n_base=None, transport=None, place_transport=None):
    if token is None:
        load_dotenv(Path(__file__).resolve().parents[2] / '.env', encoding='utf-8-sig')
        token = os.getenv('SPOT_N8N_TOKEN') or os.getenv('SPOT_API_TOKEN', '')
    n8n_base = n8n_base or os.getenv('SPOT_N8N_BASE_URL', 'https://raschepat.app.n8n.cloud')
    parsed = urlsplit(n8n_base)
    if len(token) < 24 or parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise RuntimeError('Configure an HTTPS n8n origin and a server-side token')
    sensitive = [token] + [v for k,v in os.environ.items() if v and len(v)>=8 and any(w in k.upper() for w in ('KEY','TOKEN','SECRET','PASSWORD','CLIENT_ID'))]
    client = httpx.AsyncClient(base_url=n8n_base.rstrip('/'), timeout=20, follow_redirects=False,
                              headers={'X-SPOT-API-Key':token}, transport=transport)
    sessions = {}

    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()

    app = FastAPI(title='SPOT local web', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]'])

    def failure(code, status):
        return JSONResponse({'error':{'code':code}}, status_code=status)

    @app.middleware('http')
    async def protect(request, call_next):
        # Local MVP is deliberately not served through the public research tunnel.
        if request.method == 'POST':
            origin = request.headers.get('origin')
            if origin != str(request.base_url).rstrip('/'):
                return failure('INVALID_ORIGIN', 403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' https: data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    def session(request):
        sid = request.cookies.get(COOKIE)
        record = sessions.get(sid)
        if not record or record['expires'] < time.monotonic():
            return None
        return record

    @app.get('/')
    async def index(request: Request):
        now = time.monotonic()
        for sid in list(sessions):
            if sessions[sid]['expires'] < now:
                del sessions[sid]
        response = FileResponse(STATIC/'index.html')
        if not session(request):
            if len(sessions) >= 256:
                return failure('SESSION_LIMIT', 429)
            sid = secrets.token_urlsafe(32)
            sessions[sid] = {'expires':now+3600, 'jobs':set(), 'requests':{}, 'namespace':secrets.token_hex(8), 'lock':asyncio.Lock()}
            response.set_cookie(COOKIE, sid, httponly=True, samesite='strict', max_age=3600)
        return response

    @app.get('/assets/{name}')
    async def asset(name: str):
        if name not in ('app.js','style.css','experience.js','leaflet.js','leaflet.css'):
            return failure('NOT_FOUND',404)
        return FileResponse(STATIC/name)

    @app.get('/api/config')
    async def config():
        return {'reference_date':datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(), 'local_only':True}

    async def place_request(request, operation, **kwargs):
        record = session(request)
        if not record:
            return failure('SESSION_EXPIRED',401)
        now = time.monotonic()
        recent = [at for at in record.get('place_calls',[]) if now-at < 60]
        if len(recent) >= 30:
            return failure('PLACE_RATE_LIMIT',429)
        record['place_calls'] = recent + [now]
        try:
            value = await operation(os.getenv('KAKAO_REST_API_KEY',''), transport=place_transport, **kwargs)
            return JSONResponse(redact({'results':value},sensitive))
        except places.PlaceError as exc:
            return failure(str(exc),503 if str(exc) != 'ADDRESS_NOT_FOUND' else 404)

    @app.get('/api/places/search')
    async def place_search(request: Request, q: str = ''):
        if not 2 <= len(q.strip()) <= 100:
            return failure('INVALID_PLACE_QUERY',422)
        return await place_request(request, places.search, query=q.strip())

    @app.get('/api/places/reverse')
    async def place_reverse(request: Request, lat: float, lng: float):
        if not (32 <= lat <= 39.5 and 124 <= lng <= 132):
            return failure('INVALID_COORDINATES',422)
        return await place_request(request, places.reverse, lat=lat, lng=lng)

    async def upstream(method, path, **kwargs):
        try:
            response = await client.request(method, path, **kwargs)
            if response.status_code not in (200,202):
                status = response.status_code if response.status_code in (401,403,404,409,422,429) else 503
                return None, failure({401:'CONNECTION_AUTH',403:'CONNECTION_AUTH',404:'JOB_NOT_FOUND',409:'REQUEST_CONFLICT',422:'INVALID_REQUEST',429:'BUSY'}.get(status,'CONNECTION_UNAVAILABLE'),status)
            if len(response.content)>2_000_000:
                return None, failure('INVALID_UPSTREAM',502)
            data = response.json()
            if not isinstance(data,dict) or not re.fullmatch('[a-f0-9]{32}',str(data.get('job_id',''))) or data.get('status') not in ('queued','running','completed','failed'):
                return None, failure('INVALID_UPSTREAM',502)
            return (response.status_code,redact(data,sensitive)), None
        except (httpx.HTTPError,ValueError):
            return None, failure('CONNECTION_UNAVAILABLE',503)

    @app.post('/api/research')
    async def submit(request: Request):
        record = session(request)
        if not record:
            return failure('SESSION_EXPIRED',401)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>16384:
                return failure('REQUEST_TOO_LARGE',413)
        try:
            payload = ResearchRequest.model_validate_json(bytes(body)).model_dump()
        except (ValidationError,ValueError):
            return failure('INVALID_REQUEST',422)
        async with record['lock']:
            request_id = payload['request_id']
            previous = record['requests'].get(request_id)
            if previous is not None and previous != payload:
                return failure('REQUEST_CONFLICT',409)
            if previous is None and len(record['requests']) >= 4:
                return failure('SESSION_JOB_LIMIT',429)
            # Retain exact input even on timeout, so a manual retry reuses its id.
            record['requests'][request_id] = payload
            forwarded = dict(payload)
            forwarded['request_id'] = 'web-' + record['namespace'] + '-' + hashlib.sha256(request_id.encode()).hexdigest()
            result,error = await upstream('POST','/webhook/spot-research',json=forwarded)
            if error is not None:
                return error
            status,data = result
            record['jobs'].add(data['job_id'])
            return JSONResponse(data,status_code=status)

    @app.get('/api/research/{job_id}')
    async def get_job(job_id: str, request: Request):
        record = session(request)
        if not record:
            return failure('SESSION_EXPIRED',401)
        if job_id not in record['jobs']:
            return failure('JOB_NOT_FOUND',404)
        result,error = await upstream('GET','/webhook/spot-research-status',params={'job_id':job_id})
        if error is not None:
            return error
        status,data = result
        if data['job_id'] != job_id:
            return failure('INVALID_UPSTREAM',502)
        return JSONResponse(data,status_code=status)

    return app
