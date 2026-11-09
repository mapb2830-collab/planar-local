"""Local API. Run: python -m uvicorn main:app --reload --host 127.0.0.1."""
import logging
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock, BoundedSemaphore
from typing import Annotated, Literal
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from app.models import Job, Settings
from app.geometry import load_geometry, GeometryError
from app.nesting import nest
from app.exporters import export_job, rings

app = FastAPI(title='PLANAR Studio — API local', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'], expose_headers=['Content-Disposition'])
MAX_BYTES = 20 * 1024 * 1024
jobs: OrderedDict[str, tuple[float, Job]] = OrderedDict()
lock = Lock()
processing_slot = BoundedSemaphore(1)
log = logging.getLogger('planar')


def clean_jobs():
    now = time.monotonic()
    for key, (created, _) in list(jobs.items()):
        if now-created > 3600:
            del jobs[key]
    while len(jobs) > 20:
        jobs.popitem(last=False)


def serialize(job):
    sheets = []
    nominal_area = 0
    for i, sheet in enumerate(job.sheets):
        parts = []
        area = 0
        for p in sheet:
            point = p.polygon.representative_point()
            area += p.piece.nominal_area
            parts.append({'id': p.piece.id, 'rings': rings(p.polygon), 'angle': p.angle,
                          'area': round(p.piece.nominal_area, 3), 'label': [point.x, point.y]})
        nominal_area += area
        sheets.append({'index': i, 'pieces': parts, 'utilization': round(100*area/(job.settings.width*job.settings.height), 2)})
    utilization = 100*nominal_area/(len(sheets)*job.settings.width*job.settings.height)
    return {'id': job.id, 'filename': job.filename, 'settings': job.settings.model_dump(),
            'sheets': sheets, 'preview': job.preview, 'warnings': job.warnings,
            'piece_count': sum(len(s) for s in job.sheets), 'utilization': round(utilization, 2),
            'area_mm2': round(nominal_area, 3), 'expires_in_seconds': 3600}


def process(data, filename, settings):
    extension = Path(filename).suffix.lower().lstrip('.')
    try:
        pieces, preview, warnings = load_geometry(data, extension, settings)
        sheets = nest(pieces, settings)
    except GeometryError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        log.exception('Failed parsing model')
        raise HTTPException(422, 'No se pudo interpretar el archivo. Comprueba que su contenido coincida con la extensión y que contenga geometría válida.') from exc
    job = Job(uuid4().hex, filename, settings, sheets, preview, warnings)
    with lock:
        jobs[job.id] = (time.monotonic(), job)
        clean_jobs()
    return serialize(job)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '0.1.0', 'mode': 'local'}


@app.post('/api/process')
async def process_file(file: Annotated[UploadFile, File()], settings: Annotated[str, Form()] = '{}'):
    filename = Path((file.filename or 'model').replace('\\', '/')).name
    if Path(filename).suffix.lower() not in {'.stl', '.obj', '.dxf', '.3dm', '.ply', '.off'}:
        await file.close()
        raise HTTPException(415, 'Formato no compatible. Usa STL, OBJ, DXF, 3DM, PLY u OFF.')
    try:
        options = Settings.model_validate_json(settings)
    except (ValidationError, ValueError) as exc:
        await file.close()
        raise HTTPException(422, 'Parámetros inválidos: revisa dimensiones, margen, grosor, kerf y unidades.') from exc
    data = bytearray()
    try:
        while chunk := await file.read(1024*1024):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, 'El archivo supera el límite de 20 MB.')
    finally:
        await file.close()
    if not data:
        raise HTTPException(422, 'El archivo está vacío.')
    if not processing_slot.acquire(blocking=False):
        raise HTTPException(429, 'Ya hay un modelo en proceso. Espera unos segundos e intenta de nuevo.')
    try:
        return await run_in_threadpool(process, bytes(data), filename, options)
    finally:
        processing_slot.release()


@app.get('/api/jobs/{job_id}/export/{format}')
def export(job_id: str, format: Literal['dxf', 'svg', 'pdf']):
    with lock:
        clean_jobs()
        record = jobs.get(job_id)
    if record is None:
        raise HTTPException(404, 'El trabajo expiró o el servidor se reinició. Procesa el archivo otra vez.')
    content, mime, filename = export_job(record[1], format)
    return Response(content, media_type=mime,
                    headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'})
