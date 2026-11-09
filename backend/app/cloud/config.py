"""Fail closed for public deployments; local CAD remains available offline."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Config:
    database_url: str
    supabase_url: str
    supabase_key: str
    origins: tuple[str, ...]
    storage: Path
    owner_email: str = 'marcos.pacheco@cun.edu.co'
    free_credits: int = 5
    timeout: int = 60
    testing: bool = False

    @classmethod
    def from_env(cls):
        origins = tuple(x.strip().rstrip('/') for x in os.getenv('CORS_ORIGINS', '').split(',') if x.strip())
        database = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql+psycopg://', 1)
        if database.startswith('postgresql://'):
            database = database.replace('postgresql://', 'postgresql+psycopg://', 1)
        cfg = cls(database, os.getenv('SUPABASE_URL', '').rstrip('/'), os.getenv('SUPABASE_PUBLISHABLE_KEY', ''),
                  origins, Path(os.getenv('STORAGE_PATH', '/var/data/planar')),
                  os.getenv('OWNER_EMAIL', 'marcos.pacheco@cun.edu.co').lower())
        if not database.startswith('postgresql+psycopg://') or not cfg.supabase_key:
            raise RuntimeError('Configure PostgreSQL DATABASE_URL and SUPABASE_PUBLISHABLE_KEY.')
        for origin in (*origins, cfg.supabase_url):
            p = urlparse(origin)
            if p.scheme != 'https' or not p.hostname or p.hostname in {'localhost', '127.0.0.1', '::1'} or '*' in origin or p.path not in {'', '/'} or p.query or p.fragment or p.username:
                raise RuntimeError('Only explicit public HTTPS origins are permitted.')
        if not origins or not cfg.supabase_url or not cfg.storage.is_absolute():
            raise RuntimeError('Configure CORS_ORIGINS, SUPABASE_URL and an absolute STORAGE_PATH.')
        if os.getenv('PAYMENTS_MODE', 'disabled') != 'disabled':
            raise RuntimeError('Real payments are not implemented in this release.')
        return cfg
