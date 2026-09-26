-- Lectic invited pilot. Apply only to its dedicated Supabase project.

BEGIN;


CREATE TABLE pilot_accounts (
	id VARCHAR(64) NOT NULL,
	created FLOAT NOT NULL,
	email TEXT NOT NULL,
	used_bytes BIGINT NOT NULL,
	lease VARCHAR(64),
	lease_until FLOAT NOT NULL,
	PRIMARY KEY (id)
)

;

ALTER TABLE public.pilot_accounts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_accounts FROM anon, authenticated;

CREATE POLICY own_account ON public.pilot_accounts FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = id);


CREATE TABLE pilot_backups (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_backups_owner ON pilot_backups (owner);

ALTER TABLE public.pilot_backups ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_backups FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_backups FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_budgets (
	id VARCHAR(64) NOT NULL,
	created FLOAT NOT NULL,
	committed BIGINT NOT NULL,
	PRIMARY KEY (id)
)

;

ALTER TABLE public.pilot_budgets ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_budgets FROM anon, authenticated;


CREATE TABLE pilot_calls (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	status VARCHAR(24) NOT NULL,
	reserved BIGINT NOT NULL,
	actual BIGINT,
	month VARCHAR(7) NOT NULL,
	data JSON,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_calls_owner ON pilot_calls (owner);

ALTER TABLE public.pilot_calls ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_calls FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_calls FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_captures (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	title TEXT NOT NULL,
	state VARCHAR(24) NOT NULL,
	data JSON NOT NULL,
	bytes BIGINT NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_captures_owner ON pilot_captures (owner);

ALTER TABLE public.pilot_captures ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_captures FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_captures FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_events (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	name VARCHAR(40) NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_events_owner ON pilot_events (owner);

ALTER TABLE public.pilot_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_events FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_events FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_invites (
	id VARCHAR(64) NOT NULL,
	created FLOAT NOT NULL,
	enabled INTEGER NOT NULL,
	PRIMARY KEY (id)
)

;

ALTER TABLE public.pilot_invites ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_invites FROM anon, authenticated;


CREATE TABLE pilot_jobs (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	kind VARCHAR(32) NOT NULL,
	status VARCHAR(24) NOT NULL,
	payload JSON NOT NULL,
	result JSON,
	error TEXT,
	priority INTEGER NOT NULL,
	attempts INTEGER NOT NULL,
	available FLOAT NOT NULL,
	lease_until FLOAT NOT NULL,
	cancelled INTEGER NOT NULL,
	key VARCHAR(64) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (owner, key)
)

;

CREATE INDEX ix_pilot_jobs_owner ON pilot_jobs (owner);

ALTER TABLE public.pilot_jobs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_jobs FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_jobs FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_packs (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	title TEXT NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_packs_owner ON pilot_packs (owner);

ALTER TABLE public.pilot_packs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_packs FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_packs FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_results (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	title TEXT NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_pilot_results_owner ON pilot_results (owner);

ALTER TABLE public.pilot_results ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_results FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_results FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);


CREATE TABLE pilot_shares (
	id VARCHAR(64) NOT NULL,
	owner VARCHAR(36) NOT NULL,
	created FLOAT NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	revoked INTEGER NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (token_hash)
)

;

CREATE INDEX ix_pilot_shares_owner ON pilot_shares (owner);

ALTER TABLE public.pilot_shares ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.pilot_shares FROM anon, authenticated;

CREATE POLICY owner_read ON public.pilot_shares FOR SELECT TO authenticated USING ((SELECT auth.uid())::text = owner);

INSERT INTO storage.buckets (id, name, public, file_size_limit) VALUES ('lectic-private', 'lectic-private', false, 536870912) ON CONFLICT (id) DO NOTHING;

CREATE POLICY lectic_owner_download ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'lectic-private' AND (storage.foldername(name))[1] = (SELECT auth.uid())::text);

-- Uploads are accepted only through the API, which enforces invitations and quota.

COMMIT;
