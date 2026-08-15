CREATE TABLE IF NOT EXISTS vault_placeholder_counters (
  tenant_id text NOT NULL,
  session_id text NOT NULL,
  label text NOT NULL,
  suffix text NOT NULL,
  next_value integer NOT NULL CHECK (next_value BETWEEN 1 AND 99999),
  PRIMARY KEY (tenant_id, session_id, label, suffix)
);

INSERT INTO vault_placeholder_counters (tenant_id, session_id, label, suffix, next_value)
SELECT
  tenant_id,
  session_id,
  match[1],
  COALESCE(match[3], ''),
  MAX((match[2])::integer)
FROM vault_records
CROSS JOIN LATERAL regexp_match(
  placeholder,
  '^\[([A-Z]{2,12})_([1-9][0-9]{0,4})\](#[0-9a-f]{16})?$'
) AS match
GROUP BY tenant_id, session_id, match[1], COALESCE(match[3], '')
ON CONFLICT (tenant_id, session_id, label, suffix) DO UPDATE
SET next_value = GREATEST(
  vault_placeholder_counters.next_value,
  EXCLUDED.next_value
);
