"""Entrypoint: explicit cloud deployment or the original offline workstation."""
import os

mode = os.getenv('PLANAR_MODE', 'local')
if mode not in {'local', 'cloud'}:
    raise RuntimeError('PLANAR_MODE must be local or cloud.')
if os.getenv('RENDER') and mode != 'cloud':
    raise RuntimeError('Render requires PLANAR_MODE=cloud; offline access cannot be exposed.')
if mode == 'cloud':
    from app.cloud.api import create_app
    from app.cloud.config import Config
    app = create_app(Config.from_env())
else:
    from local_api import app
