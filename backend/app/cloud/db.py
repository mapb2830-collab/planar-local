from datetime import datetime, timezone
from sqlalchemy import (MetaData, Table, Column, String, Integer, BigInteger, DateTime, JSON,
                        ForeignKey, CheckConstraint, create_engine, text)


def now():
    return datetime.now(timezone.utc)


metadata = MetaData(schema='planar')
users = Table('users', metadata,
    Column('id', String(36), primary_key=True), Column('email', String(320), nullable=False, unique=True),
    Column('name', String(100), nullable=False), Column('role', String(16), nullable=False, default='user'),
    Column('free_credits', Integer, nullable=False, default=5),
    Column('trial_credits', Integer, nullable=False, default=0),
    Column('paid_credits', Integer, nullable=False, default=0),
    Column('trial_granted', Integer, nullable=False, default=0),
    Column('storage_bytes', BigInteger, nullable=False, default=0),
    Column('file_count', Integer, nullable=False, default=0),
    Column('created_at', DateTime(timezone=True), nullable=False, default=now),
    CheckConstraint("role IN ('user','admin','owner')"),
    CheckConstraint('free_credits >= 0 AND trial_credits >= 0 AND paid_credits >= 0'),
    CheckConstraint('storage_bytes >= 0 AND file_count >= 0'))
files = Table('files', metadata,
    Column('id', String(36), primary_key=True), Column('user_id', ForeignKey('planar.users.id'), nullable=False, index=True),
    Column('filename', String(200), nullable=False), Column('extension', String(10), nullable=False),
    Column('size', BigInteger, nullable=False), Column('sha256', String(64), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False, default=now))
jobs = Table('jobs', metadata,
    Column('id', String(36), primary_key=True), Column('user_id', ForeignKey('planar.users.id'), nullable=False, index=True),
    Column('filename', String(200), nullable=False), Column('status', String(16), nullable=False),
    Column('result', JSON), Column('error', String(300)),
    Column('created_at', DateTime(timezone=True), nullable=False, default=now))
ledger = Table('credit_ledger', metadata,
    Column('id', String(36), primary_key=True), Column('user_id', ForeignKey('planar.users.id'), nullable=False, index=True),
    Column('kind', String(16), nullable=False), Column('amount', Integer, nullable=False),
    Column('operation', String(100), unique=True, nullable=False), Column('created_at', DateTime(timezone=True), nullable=False, default=now),
    CheckConstraint("kind IN ('free','trial','paid')"))
subscriptions = Table('subscriptions', metadata,
    Column('user_id', ForeignKey('planar.users.id'), primary_key=True),
    Column('plan', String(16), nullable=False, default='free'),
    Column('status', String(16), nullable=False, default='trial'),
    Column('expires_at', DateTime(timezone=True)),
    CheckConstraint("plan IN ('free','pro','premium')"), CheckConstraint("status IN ('trial','cancelled')"))
audit = Table('audit_log', metadata,
    Column('id', String(36), primary_key=True), Column('actor_id', ForeignKey('planar.users.id'), nullable=False),
    Column('action', String(50), nullable=False), Column('target_id', String(36)), Column('details', JSON),
    Column('created_at', DateTime(timezone=True), nullable=False, default=now))
settings = Table('admin_settings', metadata,
    Column('key', String(50), primary_key=True), Column('value', JSON, nullable=False))


def make_engine(config):
    if config.testing and config.database_url.startswith('sqlite:'):
        return create_engine(config.database_url, connect_args={'check_same_thread': False},
                             execution_options={'schema_translate_map': {'planar': None}})
    return create_engine(config.database_url, pool_pre_ping=True, pool_size=5, max_overflow=2,
                         connect_args={'sslmode': 'disable' if config.testing else 'require', 'connect_timeout': 10})


def initialize(engine):
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            conn.execute(text('CREATE SCHEMA IF NOT EXISTS planar'))
            conn.execute(text('REVOKE ALL ON SCHEMA planar FROM PUBLIC, anon, authenticated'))
        metadata.create_all(conn)
        if engine.dialect.name == 'postgresql':
            for table in metadata.sorted_tables:
                conn.execute(text(f'ALTER TABLE planar.{table.name} ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(f'REVOKE ALL ON planar.{table.name} FROM PUBLIC, anon, authenticated'))
        if not conn.execute(settings.select().where(settings.c.key == 'registration_open')).first():
            conn.execute(settings.insert().values(key='registration_open', value=True))
