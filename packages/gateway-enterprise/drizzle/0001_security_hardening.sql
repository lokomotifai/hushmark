CREATE TABLE IF NOT EXISTS admin_sessions (
  token_hash text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_sessions_expiry_idx ON admin_sessions(expires_at);

ALTER TABLE audit_events ALTER COLUMN seq DROP IDENTITY IF EXISTS;

-- Pre-hardening vault rows cannot be assigned to a trustworthy tenant and do not
-- contain the keyed digest needed by the new lookup path. Discard them instead of
-- silently placing them in a shared compatibility tenant.
TRUNCATE TABLE vault_records;
ALTER TABLE vault_records DROP CONSTRAINT IF EXISTS vault_records_pkey;
ALTER TABLE vault_records ADD COLUMN IF NOT EXISTS tenant_id text;
ALTER TABLE vault_records ADD COLUMN IF NOT EXISTS value_hmac text;
ALTER TABLE vault_records ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE vault_records ALTER COLUMN value_hmac SET NOT NULL;
ALTER TABLE vault_records
  ADD CONSTRAINT vault_records_pkey PRIMARY KEY (tenant_id, session_id, placeholder);
CREATE UNIQUE INDEX IF NOT EXISTS vault_records_value_hmac_uq
  ON vault_records(tenant_id, session_id, entity_type, value_hmac);
