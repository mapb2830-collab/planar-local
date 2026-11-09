-- Planar Studio 0.2: private application schema. No client-side grants.

CREATE SCHEMA IF NOT EXISTS planar;

REVOKE ALL ON SCHEMA planar FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.admin_settings (
	key VARCHAR(50) NOT NULL,
	value JSON NOT NULL,
	PRIMARY KEY (key)
)

;

ALTER TABLE planar.admin_settings ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.admin_settings FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.users (
	id VARCHAR(36) NOT NULL,
	email VARCHAR(320) NOT NULL,
	name VARCHAR(100) NOT NULL,
	role VARCHAR(16) NOT NULL,
	free_credits INTEGER NOT NULL,
	trial_credits INTEGER NOT NULL,
	paid_credits INTEGER NOT NULL,
	trial_granted INTEGER NOT NULL,
	storage_bytes BIGINT NOT NULL,
	file_count INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (role IN ('user','admin','owner')),
	CHECK (free_credits >= 0 AND trial_credits >= 0 AND paid_credits >= 0),
	CHECK (storage_bytes >= 0 AND file_count >= 0),
	UNIQUE (email)
)

;

ALTER TABLE planar.users ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.users FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.audit_log (
	id VARCHAR(36) NOT NULL,
	actor_id VARCHAR(36) NOT NULL,
	action VARCHAR(50) NOT NULL,
	target_id VARCHAR(36),
	details JSON,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(actor_id) REFERENCES planar.users (id)
)

;

ALTER TABLE planar.audit_log ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.audit_log FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.credit_ledger (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	amount INTEGER NOT NULL,
	operation VARCHAR(100) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (kind IN ('free','trial','paid')),
	FOREIGN KEY(user_id) REFERENCES planar.users (id),
	UNIQUE (operation)
)

;

CREATE INDEX IF NOT EXISTS ix_planar_credit_ledger_user_id ON planar.credit_ledger (user_id);

ALTER TABLE planar.credit_ledger ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.credit_ledger FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.files (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	filename VARCHAR(200) NOT NULL,
	extension VARCHAR(10) NOT NULL,
	size BIGINT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES planar.users (id)
)

;

CREATE INDEX IF NOT EXISTS ix_planar_files_user_id ON planar.files (user_id);

ALTER TABLE planar.files ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.files FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.jobs (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	filename VARCHAR(200) NOT NULL,
	status VARCHAR(16) NOT NULL,
	result JSON,
	error VARCHAR(300),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES planar.users (id)
)

;

CREATE INDEX IF NOT EXISTS ix_planar_jobs_user_id ON planar.jobs (user_id);

ALTER TABLE planar.jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.jobs FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS planar.subscriptions (
	user_id VARCHAR(36) NOT NULL,
	plan VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (user_id),
	CHECK (plan IN ('free','pro','premium')),
	CHECK (status IN ('trial','cancelled')),
	FOREIGN KEY(user_id) REFERENCES planar.users (id)
)

;

ALTER TABLE planar.subscriptions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON planar.subscriptions FROM PUBLIC, anon, authenticated;

INSERT INTO planar.admin_settings (key,value) VALUES ('registration_open','true'::json) ON CONFLICT (key) DO NOTHING;
