import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from threading import BoundedSemaphore
from typing import Annotated, Literal
from uuid import UUID, uuid4
import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, update, text
from starlette.concurrency import run_in_threadpool
from .auth import current_user, administrator, owner
from .db import make_engine, initialize, users, files, jobs, ledger, subscriptions, audit, settings as admin_settings, now
from ..models import Settings

log = logging.getLogger('uvicorn.error')
MAX_BYTES = 20 * 1024**2
MAX_STORAGE = 100 * 1024**2
PROCESSABLE = {'.stl', '.obj', '.dxf', '.3dm', '.ply', '.off'}
ARCHIVE = PROCESSABLE | {'.rvt', '.ifc', '.dwg', '.skp'}


class BodyLimit:
    """Bound streamed request bodies before multipart spooling can fill the disk."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        total, exceeded = 0, False

        async def limited():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get('body', b''))
            if total > MAX_BYTES + 64 * 1024:
                exceeded = True
                raise HTTPException(413, 'El archivo supera el límite de 20 MB.')
            return message

        async def guarded(message):
            if exceeded and message['type'] == 'http.response.start':
                message['status'] = 413
            await send(message)
        await self.app(scope, limited, guarded)


def clean_name(name):
    name = Path((name or 'modelo').replace('\\', '/')).name
    return ''.join(c for c in name if c.isprintable() and c not in {'"', ';'})[:200] or 'modelo'


async def read_upload(file, allowed):
    name = clean_name(file.filename)
    try:
        if Path(name).suffix.lower() not in allowed:
            raise HTTPException(415, 'Formato no procesable. RVT, IFC, DWG y SKP se guardan en Archivos; exporta STL, OBJ o DXF para cortar.')
        data = bytearray()
        while chunk := await file.read(1024**2):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, 'El archivo supera el límite de 20 MB.')
        if not data:
            raise HTTPException(422, 'El archivo está vacío.')
        return name, bytes(data)
    finally:
        await file.close()


def event(conn, actor, action, target=None, details=None):
    conn.execute(audit.insert().values(id=str(uuid4()), actor_id=actor, action=action, target_id=target, details=details or {}))


def recover(engine):
    # Single-instance service. A restart refunds interrupted work exactly once.
    with engine.begin() as conn:
        pending = conn.execute(jobs.select().where(jobs.c.status == 'processing').with_for_update()).mappings().all()
        for job in pending:
            conn.execute(users.update().where(users.c.id == job['user_id']).values(free_credits=users.c.free_credits + 1))
            conn.execute(ledger.insert().values(id=str(uuid4()), user_id=job['user_id'], kind='free', amount=1, operation='refund:' + job['id']))
            conn.execute(jobs.update().where(jobs.c.id == job['id']).values(status='failed', error='Proceso interrumpido. Crédito devuelto.'))


def run_job(app, uid, name, data, options):
    engine, cfg = app.state.engine, app.state.config
    job_id = str(uuid4())
    with engine.begin() as conn:
        reserved = conn.execute(users.update().where(users.c.id == uid, users.c.free_credits > 0)
                                .values(free_credits=users.c.free_credits - 1))
        if not reserved.rowcount:
            raise HTTPException(402, 'No quedan créditos gratuitos. Los cobros reales aún no están disponibles.')
        # Trial/paid balances never authorize real processing in this release.
        conn.execute(ledger.insert().values(id=str(uuid4()), user_id=uid, kind='free', amount=-1, operation='process:' + job_id))
        conn.execute(jobs.insert().values(id=job_id, user_id=uid, filename=name, status='processing'))
    destination = cfg.storage / 'jobs' / job_id
    try:
        if shutil.disk_usage(cfg.storage).free < 512 * 1024**2:
            raise HTTPException(507, 'Almacenamiento temporalmente lleno.')
        with tempfile.TemporaryDirectory(prefix='cad-', dir=cfg.storage / 'tmp') as directory:
            folder = Path(directory)
            (folder / 'input.bin').write_bytes(data)
            (folder / 'input.json').write_text(json.dumps({'filename': name, 'settings': options.model_dump()}))
            env = {k: v for k, v in os.environ.items() if k in {'PATH', 'SYSTEMROOT', 'WINDIR', 'LANG', 'TMPDIR'}}
            env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONUNBUFFERED='1')
            try:
                completed = subprocess.run([sys.executable, '-m', 'app.worker', directory], cwd=Path(__file__).resolve().parents[2],
                    env=env, timeout=cfg.timeout, capture_output=True)
            except subprocess.TimeoutExpired:
                raise HTTPException(422, 'El modelo superó 60 segundos. Simplifica la geometría; el crédito se devolverá.')
            if completed.returncode:
                detail = json.loads((folder / 'error.json').read_text())['detail'] if (folder / 'error.json').exists() else 'No se pudo procesar el modelo dentro de los límites de memoria y complejidad.'
                raise HTTPException(422, detail)
            payload = json.loads((folder / 'output.json').read_text())
            payload['result']['id'] = job_id
            destination.mkdir(mode=0o700)
            for fmt in ('svg', 'dxf', 'pdf'):
                shutil.move(str(folder / fmt), destination / fmt)
            with engine.begin() as conn:
                conn.execute(jobs.update().where(jobs.c.id == job_id).values(status='completed', result=payload))
                event(conn, uid, 'process.completed', job_id)
            return payload['result']
    except Exception as exc:
        shutil.rmtree(destination, ignore_errors=True)
        detail = str(exc.detail)[:300] if isinstance(exc, HTTPException) else 'No se pudo completar el trabajo. Crédito devuelto.'
        with engine.begin() as conn:
            conn.execute(users.update().where(users.c.id == uid).values(free_credits=users.c.free_credits + 1))
            conn.execute(ledger.insert().values(id=str(uuid4()), user_id=uid, kind='free', amount=1, operation='refund:' + job_id))
            conn.execute(jobs.update().where(jobs.c.id == job_id).values(status='failed', error=detail))
        if isinstance(exc, HTTPException):
            raise
        log.error('job_failed job=%s type=%s', job_id, type(exc).__name__)
        raise HTTPException(500, detail) from exc


class Simulation(BaseModel):
    user_id: UUID
    plan: Literal['free', 'pro', 'premium']
    credits: int = Field(ge=0, le=100)
    request_id: UUID


class RoleChange(BaseModel):
    role: Literal['user', 'admin']


class RegistrationSetting(BaseModel):
    registration_open: bool


def create_app(config):
    engine = make_engine(config)

    @asynccontextmanager
    async def lifespan(app):
        initialize(engine)
        for directory in ('files', 'jobs', 'tmp'):
            (config.storage / directory).mkdir(parents=True, exist_ok=True, mode=0o700)
        # Only one API process is supported; its persistent disk serializes deployments.
        recover(engine)
        for item in (config.storage / 'tmp').iterdir():
            if item.is_dir():
                shutil.rmtree(item)
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            app.state.auth_http = client
            yield
        engine.dispose()

    app = FastAPI(title='Planar Studio API', version='0.2.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.config, app.state.engine, app.state.processing = config, engine, BoundedSemaphore(1)
    app.add_middleware(BodyLimit)
    app.add_middleware(CORSMiddleware, allow_origins=list(config.origins), allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type'], expose_headers=['Content-Disposition'])

    @app.middleware('http')
    async def headers_and_logs(request, call_next):
        started, request_id = time.monotonic(), str(uuid4())
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store', 'X-Request-ID': request_id})
        # Do not log tokens, query strings, uploaded names, or user emails.
        route = request.scope.get('route')
        log.info('request id=%s method=%s route=%s status=%s ms=%d', request_id, request.method,
                 getattr(route, 'path', 'unmatched'), response.status_code, (time.monotonic() - started) * 1000)
        return response

    @app.get('/api/health')
    def health():
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            with tempfile.TemporaryFile(dir=config.storage / 'tmp') as probe:
                probe.write(b'ok')
            return {'status': 'ok', 'version': '0.2.0', 'mode': 'cloud', 'payments': 'disabled'}
        except Exception:
            return JSONResponse({'status': 'unavailable'}, status_code=503)

    @app.get('/api/me')
    def me(user=Depends(current_user)):
        with engine.connect() as conn:
            subscription = conn.execute(subscriptions.select().where(subscriptions.c.user_id == user['id'])).mappings().first()
        return {**user, 'subscription': dict(subscription) if subscription else None, 'payments': 'disabled'}

    @app.get('/api/credits')
    def credits(user=Depends(current_user)):
        with engine.connect() as conn:
            return list(conn.execute(ledger.select().where(ledger.c.user_id == user['id']).order_by(ledger.c.created_at.desc()).limit(100)).mappings())

    @app.get('/api/files')
    def list_files(user=Depends(current_user)):
        with engine.connect() as conn:
            return list(conn.execute(files.select().where(files.c.user_id == user['id']).order_by(files.c.created_at.desc())).mappings())

    @app.post('/api/files', status_code=201)
    async def upload(file: Annotated[UploadFile, File()], user=Depends(current_user)):
        name, data = await read_upload(file, ARCHIVE)
        file_id = str(uuid4())
        record = dict(id=file_id, user_id=user['id'], filename=name, extension=Path(name).suffix.lower(),
                      size=len(data), sha256=hashlib.sha256(data).hexdigest())
        path = config.storage / 'files' / file_id
        try:
            with engine.begin() as conn:
                reserved = conn.execute(users.update().where(users.c.id == user['id'], users.c.file_count < 20,
                    users.c.storage_bytes + len(data) <= MAX_STORAGE).values(storage_bytes=users.c.storage_bytes + len(data), file_count=users.c.file_count + 1))
                if not reserved.rowcount:
                    raise HTTPException(413, 'Límite de biblioteca: 20 archivos o 100 MB. Elimina archivos para continuar.')
                if shutil.disk_usage(config.storage).free < 512 * 1024**2:
                    raise HTTPException(507, 'Almacenamiento temporalmente lleno.')
                with path.open('xb') as output:
                    output.write(data)
                path.chmod(0o600)
                conn.execute(files.insert().values(**record))
                event(conn, user['id'], 'file.uploaded', file_id)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return record

    def owned(table, identifier, uid):
        with engine.connect() as conn:
            row = conn.execute(table.select().where(table.c.id == str(identifier), table.c.user_id == uid)).mappings().first()
        if not row:
            raise HTTPException(404, 'No se encontró el recurso.')
        return row

    @app.get('/api/files/{file_id}/download')
    def download_file(file_id: UUID, user=Depends(current_user)):
        row = owned(files, file_id, user['id'])
        path = config.storage / 'files' / str(file_id)
        if not path.is_file():
            raise HTTPException(410, 'El archivo no está disponible. Contacta al administrador.')
        return FileResponse(path, filename=row['filename'], media_type='application/octet-stream')

    @app.delete('/api/files/{file_id}', status_code=204)
    def delete_file(file_id: UUID, user=Depends(current_user)):
        with engine.begin() as conn:
            row = conn.execute(files.delete().where(files.c.id == str(file_id), files.c.user_id == user['id']).returning(files.c.size)).first()
            if not row:
                raise HTTPException(404, 'No se encontró el recurso.')
            conn.execute(users.update().where(users.c.id == user['id']).values(storage_bytes=users.c.storage_bytes - row.size, file_count=users.c.file_count - 1))
            event(conn, user['id'], 'file.deleted', str(file_id))
        (config.storage / 'files' / str(file_id)).unlink(missing_ok=True)

    @app.post('/api/process')
    async def process_file(file: Annotated[UploadFile, File()], settings: Annotated[str, Form()] = '{}', user=Depends(current_user)):
        try:
            options = Settings.model_validate_json(settings)
        except (ValidationError, ValueError):
            await file.close()
            raise HTTPException(422, 'Parámetros inválidos. Revisa las medidas y unidades.')
        name, data = await read_upload(file, PROCESSABLE)
        if not app.state.processing.acquire(blocking=False):
            raise HTTPException(429, 'El motor está ocupado. Intenta de nuevo en unos segundos.', headers={'Retry-After': '10'})
        try:
            return await run_in_threadpool(run_job, app, user['id'], name, data, options)
        finally:
            app.state.processing.release()

    @app.get('/api/jobs')
    def history(user=Depends(current_user)):
        with engine.connect() as conn:
            return list(conn.execute(select(jobs.c.id, jobs.c.filename, jobs.c.status, jobs.c.error, jobs.c.created_at)
                .where(jobs.c.user_id == user['id']).order_by(jobs.c.created_at.desc()).limit(100)).mappings())

    @app.get('/api/jobs/{job_id}')
    def job_detail(job_id: UUID, user=Depends(current_user)):
        row = owned(jobs, job_id, user['id'])
        if row['status'] != 'completed':
            raise HTTPException(409, row['error'] or 'El trabajo sigue en proceso.')
        return row['result']['result']

    @app.get('/api/jobs/{job_id}/export/{format}')
    def export(job_id: UUID, format: Literal['svg', 'dxf', 'pdf'], user=Depends(current_user)):
        row = owned(jobs, job_id, user['id'])
        if row['status'] != 'completed':
            raise HTTPException(409, 'El trabajo no está listo para exportar.')
        path = config.storage / 'jobs' / str(job_id) / format
        if not path.is_file():
            raise HTTPException(410, 'Exportación no disponible. Contacta al administrador.')
        info = row['result']['exports'][format]
        return FileResponse(path, filename=info['filename'], media_type=info['mime'])

    @app.post('/api/subscription/cancel')
    def cancel(user=Depends(current_user)):
        with engine.begin() as conn:
            conn.execute(subscriptions.update().where(subscriptions.c.user_id == user['id']).values(status='cancelled'))
            event(conn, user['id'], 'subscription.trial_cancelled', user['id'])
        return {'status': 'cancelled', 'simulated': True}

    @app.post('/api/checkout')
    def checkout(user=Depends(current_user)):
        raise HTTPException(403, 'Los pagos reales están deshabilitados. Solo un administrador puede registrar simulaciones.')

    @app.get('/api/admin')
    def admin(user=Depends(administrator)):
        with engine.connect() as conn:
            return {'users': list(conn.execute(users.select().order_by(users.c.created_at.desc()).limit(200)).mappings()),
                    'audit': list(conn.execute(audit.select().order_by(audit.c.created_at.desc()).limit(100)).mappings()),
                    'settings': {row.key: row.value for row in conn.execute(admin_settings.select())},
                    'jobs_count': conn.scalar(select(func.count()).select_from(jobs))}

    @app.post('/api/admin/simulations')
    def simulate(body: Simulation, actor=Depends(administrator)):
        uid, operation = str(body.user_id), 'simulation:' + str(body.request_id)
        with engine.begin() as conn:
            # Lock target first: retries and concurrent grants cannot exceed lifetime cap.
            target = conn.execute(users.select().where(users.c.id == uid).with_for_update()).mappings().first()
            if not target:
                raise HTTPException(404, 'Usuario no encontrado.')
            if conn.execute(ledger.select().where(ledger.c.operation == operation)).first():
                return {'simulated': True, 'duplicate': True}
            if target['trial_granted'] + body.credits > 1000:
                raise HTTPException(409, 'Límite de simulación: 1000 créditos por cuenta en esta beta.')
            conn.execute(users.update().where(users.c.id == uid).values(trial_credits=users.c.trial_credits + body.credits, trial_granted=users.c.trial_granted + body.credits))
            conn.execute(ledger.insert().values(id=str(uuid4()), user_id=uid, kind='trial', amount=body.credits, operation=operation))
            conn.execute(subscriptions.delete().where(subscriptions.c.user_id == uid))
            conn.execute(subscriptions.insert().values(user_id=uid, plan=body.plan, status='trial', expires_at=now() + timedelta(days=14)))
            event(conn, actor['id'], 'purchase.simulated', uid, {'plan': body.plan, 'credits': body.credits, 'request_id': str(body.request_id)})
        return {'simulated': True, 'paid_credits': 0}

    @app.patch('/api/admin/users/{user_id}/role')
    def change_role(user_id: UUID, body: RoleChange, actor=Depends(owner)):
        with engine.begin() as conn:
            changed = conn.execute(users.update().where(users.c.id == str(user_id), users.c.role != 'owner').values(role=body.role))
            if not changed.rowcount:
                raise HTTPException(409, 'Usuario inexistente o propietario protegido.')
            event(conn, actor['id'], 'role.changed', str(user_id), {'role': body.role})
        return {'role': body.role}

    @app.patch('/api/admin/settings')
    def update_settings(body: RegistrationSetting, actor=Depends(owner)):
        with engine.begin() as conn:
            conn.execute(admin_settings.update().where(admin_settings.c.key == 'registration_open').values(value=body.registration_open))
            event(conn, actor['id'], 'settings.changed', details=body.model_dump())
        return body

    return app
