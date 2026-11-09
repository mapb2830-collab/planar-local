from uuid import UUID, uuid4
import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from .db import users, ledger, settings

bearer = HTTPBearer(auto_error=False)


async def verified_identity(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Inicia sesión para continuar.', headers={'WWW-Authenticate': 'Bearer'})
    config = request.app.state.config
    try:
        response = await request.app.state.auth_http.get(config.supabase_url + '/auth/v1/user',
            headers={'Authorization': 'Bearer ' + credentials.credentials, 'apikey': config.supabase_key})
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'El servicio de identidad no está disponible. Intenta de nuevo.') from exc
    if response.status_code in (401, 403):
        raise HTTPException(401, 'La sesión expiró. Inicia sesión de nuevo.')
    if response.status_code != 200:
        raise HTTPException(503, 'No se pudo verificar la sesión.')
    identity = response.json()
    if not identity.get('email_confirmed_at') or not identity.get('email'):
        raise HTTPException(403, 'Verifica tu correo antes de entrar al estudio.')
    try:
        identity['id'] = str(UUID(identity['id']))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Identidad inválida.')
    return identity


def current_user(request: Request, identity=Depends(verified_identity)):
    engine, cfg = request.app.state.engine, request.app.state.config
    uid = identity['id']
    # Roles come only from our private database, never editable Auth user_metadata.
    with engine.connect() as conn:
        record = conn.execute(users.select().where(users.c.id == uid)).mappings().first()
    if record:
        return dict(record)
    try:
        with engine.begin() as conn:
            enabled = conn.execute(settings.select().where(settings.c.key == 'registration_open')).mappings().one()
            if not enabled['value']:
                raise HTTPException(403, 'El acceso a la beta está temporalmente cerrado.')
            conn.execute(users.insert().values(id=uid, email=identity['email'].lower(),
                name=str(identity.get('user_metadata', {}).get('name') or identity['email'].split('@')[0])[:100],
                free_credits=cfg.free_credits))
            conn.execute(ledger.insert().values(id=str(uuid4()), user_id=uid, kind='free', amount=cfg.free_credits, operation='welcome:' + uid))
    except IntegrityError:
        pass  # A simultaneous first request may have inserted the same verified identity.
    with engine.connect() as conn:
        record = conn.execute(users.select().where(users.c.id == uid)).mappings().first()
        if not record:
            raise HTTPException(409, 'El correo ya está asociado a otra cuenta. Contacta al propietario.')
        return dict(record)


def administrator(user=Depends(current_user)):
    if user['role'] not in {'admin', 'owner'}:
        raise HTTPException(403, 'Esta acción requiere permisos de administración.')
    return user


def owner(user=Depends(administrator)):
    if user['role'] != 'owner':
        raise HTTPException(403, 'Esta acción requiere al propietario.')
    return user
