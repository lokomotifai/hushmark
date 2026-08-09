CREATE TABLE roles (
  name text PRIMARY KEY CHECK (name IN ('admin', 'operator', 'auditor'))
);

INSERT INTO roles (name) VALUES ('admin'), ('operator'), ('auditor');

CREATE TABLE users (
  id uuid PRIMARY KEY,
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text NOT NULL REFERENCES roles(name),
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  prefix text NOT NULL UNIQUE,
  secret_hash text NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policies (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  priority integer NOT NULL,
  api_key_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  allowed_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
  document jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX policies_priority_idx ON policies(priority DESC);

CREATE TABLE audit_events (
  seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts timestamptz NOT NULL,
  kind text NOT NULL,
  actor text NOT NULL,
  session_id text,
  request_sha256 text NOT NULL,
  entities jsonb NOT NULL DEFAULT '[]'::jsonb,
  prev_hash text NOT NULL,
  hash text NOT NULL
);

CREATE TABLE vault_records (
  session_id text NOT NULL,
  placeholder text NOT NULL,
  ciphertext bytea NOT NULL,
  iv bytea NOT NULL,
  tag bytea NOT NULL,
  wrapped_key text NOT NULL,
  entity_type text NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (session_id, placeholder)
);
CREATE INDEX vault_records_expiry_idx ON vault_records(expires_at);

CREATE TABLE providers (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('openai', 'anthropic')),
  base_url text NOT NULL,
  auth text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
