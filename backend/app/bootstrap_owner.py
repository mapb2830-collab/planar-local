"""Run only in the authenticated provider console AFTER verified owner login."""
from sqlalchemy import select
from app.cloud.config import Config
from app.cloud.db import make_engine, users
from app.cloud.api import event


def bootstrap(engine, email):
    with engine.begin() as conn:
        # Serializes initial ownership assignment across consoles in PostgreSQL.
        if engine.dialect.name == 'postgresql':
            conn.exec_driver_sql('LOCK TABLE planar.users IN EXCLUSIVE MODE')
        existing = conn.execute(select(users.c.id).where(users.c.role == 'owner')).first()
        if existing:
            raise RuntimeError('An owner already exists. No changes made.')
        user = conn.execute(users.select().where(users.c.email == email.lower()).with_for_update()).mappings().first()
        if not user:
            raise RuntimeError('Owner must confirm their email and sign in to the cloud API first.')
        conn.execute(users.update().where(users.c.id == user['id']).values(role='owner'))
        event(conn, user['id'], 'owner.bootstrapped', user['id'])


if __name__ == '__main__':
    cfg = Config.from_env()
    bootstrap(make_engine(cfg), cfg.owner_email)
    print('Verified account promoted to owner. No password was created.')
