CREATE TABLE IF NOT EXISTS vault_session_keys (
  tenant_id text NOT NULL,
  session_id text NOT NULL,
  wrapped_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, session_id)
);

INSERT INTO vault_session_keys (tenant_id, session_id, wrapped_key)
SELECT DISTINCT ON (tenant_id, session_id)
  tenant_id, session_id, wrapped_key
FROM vault_records
ORDER BY tenant_id, session_id, placeholder
ON CONFLICT (tenant_id, session_id) DO NOTHING;
