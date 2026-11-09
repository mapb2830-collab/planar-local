"""Isolated, time/memory bounded CAD job. No application credentials in child env."""
import json
import os
import sys
from pathlib import Path


def main():
    if sys.platform != 'win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    from fastapi import HTTPException
    from local_api import process, jobs
    from app.models import Settings
    from app.exporters import export_job
    folder = Path(sys.argv[1])
    payload = json.loads((folder / 'input.json').read_text())
    try:
        result = process((folder / 'input.bin').read_bytes(), payload['filename'], Settings(**payload['settings']))
        job = jobs[result['id']][1]
        manifest = {}
        for fmt in ('svg', 'dxf', 'pdf'):
            content, mime, name = export_job(job, fmt)
            (folder / fmt).write_bytes(content.encode() if isinstance(content, str) else content)
            manifest[fmt] = {'mime': mime, 'filename': name}
        result.pop('expires_in_seconds', None)
        (folder / 'output.json').write_text(json.dumps({'result': result, 'exports': manifest}))
    except HTTPException as exc:
        (folder / 'error.json').write_text(json.dumps({'detail': exc.detail}))
        sys.exit(2)


if __name__ == '__main__':
    main()
