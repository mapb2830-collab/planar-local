"""Cloud contract tests with real DB/files/CAD and a mocked identity provider."""
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.cloud.api import create_app, recover
from app.cloud.api import run_job
from app.models import Settings
from fastapi import HTTPException
from app.cloud.config import Config
from app.cloud.db import users, ledger, jobs, metadata
from app.bootstrap_owner import bootstrap

ALICE, BOB, OWNER, UNVERIFIED = [str(uuid4()) for _ in range(4)]
IDENTITIES = {
    'alice': {'id': ALICE, 'email': 'alice@example.test', 'email_confirmed_at': '2026-01-01', 'user_metadata': {'name': 'Alice', 'role': 'owner'}},
    'bob': {'id': BOB, 'email': 'bob@example.test', 'email_confirmed_at': '2026-01-01'},
    'owner': {'id': OWNER, 'email': 'marcos.pacheco@cun.edu.co', 'email_confirmed_at': '2026-01-01'},
    'unverified': {'id': UNVERIFIED, 'email': 'unverified@example.test'},
}


def auth(token):
    return {'Authorization': 'Bearer ' + token}


def provider(request):
    identity = IDENTITIES.get(request.headers.get('authorization', '').removeprefix('Bearer '))
    return httpx.Response(200, json=identity) if identity else httpx.Response(401, json={})


@pytest.fixture
def cloud(tmp_path):
    cfg = Config(os.getenv('TEST_DATABASE_URL', f'sqlite:///{tmp_path}/test.db'),
                 'https://identity.example.test', 'test-public-key', ('https://planar.example.test',), tmp_path / 'data', testing=True)
    app = create_app(cfg)
    if os.getenv('TEST_DATABASE_URL'):
        # A dedicated ephemeral container DB, never the deployment database.
        with app.state.engine.begin() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS planar CASCADE'))
            conn.execute(text("DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
            conn.execute(text("DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    with TestClient(app) as client:
        app.state.auth_http = httpx.AsyncClient(transport=httpx.MockTransport(provider))
        for token in ('alice', 'bob', 'owner'):
            assert client.get('/api/me', headers=auth(token)).status_code == 200
        yield client, app, cfg


def process(client, token='alice', content=None):
    if content is None:
        content = (Path(__file__).resolve().parents[2] / 'examples/pabellon.obj').read_bytes()
    return client.post('/api/process', headers=auth(token), files={'file': ('pabellon.obj', content)})


def test_requires_verified_identity_and_ignores_claimed_role(cloud):
    c, app, cfg = cloud
    assert c.get('/api/me').status_code == 401
    assert c.get('/api/me', headers=auth('forged')).status_code == 401
    assert c.get('/api/me', headers=auth('unverified')).status_code == 403
    assert c.get('/api/me', headers=auth('alice')).json()['role'] == 'user'
    assert c.get('/api/admin', headers=auth('alice')).status_code == 403
    assert c.get('/api/me', headers=auth('owner')).json()['role'] == 'user'
    bootstrap(app.state.engine, cfg.owner_email)
    assert c.get('/api/admin', headers=auth('owner')).status_code == 200
    with pytest.raises(RuntimeError, match='already exists'):
        bootstrap(app.state.engine, cfg.owner_email)


def test_protected_roles_registration_and_audit(cloud):
    c, app, cfg = cloud
    bootstrap(app.state.engine, cfg.owner_email)
    assert c.patch(f'/api/admin/users/{BOB}/role', json={'role': 'admin'}, headers=auth('alice')).status_code == 403
    assert c.patch(f'/api/admin/users/{BOB}/role', json={'role': 'admin'}, headers=auth('owner')).status_code == 200
    assert c.get('/api/admin', headers=auth('bob')).status_code == 200
    assert c.patch(f'/api/admin/users/{ALICE}/role', json={'role': 'admin'}, headers=auth('bob')).status_code == 403
    assert c.patch(f'/api/admin/users/{OWNER}/role', json={'role': 'user'}, headers=auth('owner')).status_code == 409
    assert c.patch('/api/admin/settings', json={'registration_open': False}, headers=auth('owner')).status_code == 200
    new_identity = {**IDENTITIES['alice'], 'id': str(uuid4()), 'email': 'new@example.test'}
    app.state.auth_http = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=new_identity)))
    assert c.get('/api/me', headers=auth('new')).status_code == 403


def test_file_ownership_safe_names_rvt_and_deletion(cloud):
    c, app, cfg = cloud
    r = c.post('/api/files', files={'file': ('../../model.rvt', b'architecture archive')}, headers=auth('alice'))
    assert r.status_code == 201, r.text
    row = r.json()
    assert row['filename'] == 'model.rvt'
    assert (cfg.storage / 'files' / row['id']).read_bytes() == b'architecture archive'
    assert c.get('/api/files', headers=auth('bob')).json() == []
    path = f"/api/files/{row['id']}"
    assert c.get(path + '/download', headers=auth('bob')).status_code == 404
    assert c.delete(path, headers=auth('bob')).status_code == 404
    assert c.get(path + '/download', headers=auth('alice')).headers['x-content-type-options'] == 'nosniff'
    assert c.post('/api/process', files={'file': ('model.rvt', b'revit')}, headers=auth('alice')).status_code == 415
    assert c.post('/api/files', files={'file': ('script.html', b'html')}, headers=auth('alice')).status_code == 415
    assert c.delete(path, headers=auth('alice')).status_code == 204
    assert c.delete(path, headers=auth('alice')).status_code == 404
    assert c.get('/api/me', headers=auth('alice')).json()['storage_bytes'] == 0


def test_upload_caps(cloud):
    c, app, cfg = cloud
    r = c.post('/api/files', files={'file': ('huge.rvt', b'x' * (21 * 1024**2))}, headers=auth('alice'))
    assert r.status_code == 413
    with app.state.engine.begin() as conn:
        conn.execute(users.update().where(users.c.id == ALICE).values(file_count=20))
    assert c.post('/api/files', files={'file': ('one.obj', b'v 0 0 0')}, headers=auth('alice')).status_code == 413


def test_cad_persistence_exports_ownership_and_refund(cloud):
    c, app, cfg = cloud
    r = process(c)
    assert r.status_code == 200, r.text
    job_id = r.json()['id']
    assert r.json()['piece_count'] == 5
    assert c.get('/api/me', headers=auth('alice')).json()['free_credits'] == 4
    for fmt in ('svg', 'dxf', 'pdf'):
        assert c.get(f'/api/jobs/{job_id}/export/{fmt}', headers=auth('alice')).status_code == 200
        assert c.get(f'/api/jobs/{job_id}/export/{fmt}', headers=auth('bob')).status_code == 404
    assert c.get('/api/jobs', headers=auth('bob')).json() == []
    assert process(c, content=b'broken').status_code == 422
    assert c.get('/api/me', headers=auth('alice')).json()['free_credits'] == 4
    restarted = create_app(cfg)
    with TestClient(restarted) as again:
        restarted.state.auth_http = httpx.AsyncClient(transport=httpx.MockTransport(provider))
        assert again.get(f'/api/jobs/{job_id}', headers=auth('alice')).json()['id'] == job_id
        assert again.get(f'/api/jobs/{job_id}/export/pdf', headers=auth('alice')).content.startswith(b'%PDF')


def test_trial_purchase_is_private_bounded_idempotent_and_not_spendable(cloud):
    c, app, cfg = cloud
    bootstrap(app.state.engine, cfg.owner_email)
    payload = {'user_id': ALICE, 'plan': 'premium', 'credits': 100, 'request_id': str(uuid4())}
    assert c.post('/api/admin/simulations', json=payload, headers=auth('alice')).status_code == 403
    assert c.post('/api/checkout', json=payload, headers=auth('alice')).status_code == 403
    assert c.post('/api/admin/simulations', json=payload, headers=auth('owner')).status_code == 200
    assert c.post('/api/admin/simulations', json=payload, headers=auth('owner')).json()['duplicate'] is True
    balance = c.get('/api/me', headers=auth('alice')).json()
    assert balance['trial_credits'] == 100 and balance['paid_credits'] == 0
    assert balance['subscription']['plan'] == 'premium'
    with app.state.engine.begin() as conn:
        conn.execute(users.update().where(users.c.id == ALICE).values(free_credits=0, trial_granted=1000))
    assert process(c).status_code == 402
    payload['request_id'] = str(uuid4())
    assert c.post('/api/admin/simulations', json=payload, headers=auth('owner')).status_code == 409
    assert c.post('/api/subscription/cancel', json={}, headers=auth('alice')).status_code == 200
    assert c.get('/api/me', headers=auth('alice')).json()['subscription']['status'] == 'cancelled'


def test_interrupted_work_refunds_once(cloud):
    c, app, cfg = cloud
    jid = str(uuid4())
    with app.state.engine.begin() as conn:
        conn.execute(users.update().where(users.c.id == ALICE).values(free_credits=4))
        conn.execute(jobs.insert().values(id=jid, user_id=ALICE, filename='test.obj', status='processing'))
    recover(app.state.engine)
    recover(app.state.engine)
    assert c.get('/api/me', headers=auth('alice')).json()['free_credits'] == 5
    with app.state.engine.connect() as conn:
        refunds = conn.execute(ledger.select().where(ledger.c.operation == 'refund:' + jid)).all()
    assert len(refunds) == 1


def test_cors_health_and_no_public_api_access(cloud):
    c, app, cfg = cloud
    assert c.get('/api/health').json()['payments'] == 'disabled'
    headers = {'Origin': cfg.origins[0], 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization'}
    assert c.options('/api/process', headers=headers).headers['access-control-allow-origin'] == cfg.origins[0]
    headers['Origin'] = 'https://attacker.example.test'
    assert c.options('/api/process', headers=headers).status_code == 400
    if app.state.engine.dialect.name == 'postgresql':
        with app.state.engine.connect() as conn:
            assert not conn.scalar(text("SELECT has_schema_privilege('anon', 'planar', 'USAGE')"))
            assert not conn.scalar(text("SELECT has_schema_privilege('authenticated', 'planar', 'USAGE')"))
            assert conn.scalar(text("SELECT bool_and(relrowsecurity) FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='planar' AND relkind='r'"))


def test_production_config_fails_closed(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:password@db.example.test/postgres')
    monkeypatch.setenv('SUPABASE_URL', 'https://auth.example.test')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'public-key')
    monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:5173')
    with pytest.raises(RuntimeError, match='HTTPS'):
        Config.from_env()
    monkeypatch.setenv('CORS_ORIGINS', 'https://planar.example.test')
    assert Config.from_env().database_url.startswith('postgresql+psycopg://')
    monkeypatch.setenv('PAYMENTS_MODE', 'live')
    with pytest.raises(RuntimeError, match='payments'):
        Config.from_env()


def test_last_free_credit_cannot_be_spent_twice(cloud):
    c, app, cfg = cloud
    with app.state.engine.begin() as conn:
        conn.execute(users.update().where(users.c.id == ALICE).values(free_credits=1))
    data = (Path(__file__).resolve().parents[2] / 'examples/pabellon.obj').read_bytes()
    def attempt():
        try:
            run_job(app, ALICE, 'pabellon.obj', data, Settings())
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [200, 402]
    assert c.get('/api/me', headers=auth('alice')).json()['free_credits'] == 0
