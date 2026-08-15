# Single-host community production pilot

Use this package for a controlled pilot on one Linux host. It deliberately avoids Kubernetes and
does not provision cloud resources. Do not activate it until a real pilot, demo, or integration has
an owner and an end date.

This is the **community/open-core pilot profile**. It does not provide the persistent encrypted
vault, HMAC-protected audit chain, admin console, or Madde 12 report supplied by the enterprise
runtime. Do not use this profile when those controls are part of the acceptance criteria.

The pilot topology contains only three containers:

- `core`, reachable only on an internal Docker network, with the adopted ONNX model mounted
  read-only;
- `gateway`, reachable only by the edge proxy and authenticated with `hm_k1_...` client keys; and
- Caddy, the sole public service, terminating HTTPS on ports 80 and 443.

The Hushmark images are pinned to their signed v0.1.1 manifest digests, and the official Caddy
image is pinned by digest. Evaluation PostgreSQL, Vault dev mode, the fake provider, bundled
passwords, the enterprise console, and model weights are not present.

## Host contract

Use Ubuntu 24.04 or another supported Linux distribution on `amd64` or `arm64`, Docker Engine with
Compose v2, at least 2 CPU cores and 8 GiB memory, a fully qualified domain name, and these paths:

```text
/opt/hushmark/repo/                         # clean repository checkout at an approved ref
/etc/hushmark/production.env               # mode 0600, non-secret deployment settings
/etc/hushmark/secrets/api-keys              # mode 0600, required
/etc/hushmark/secrets/openai-api-key        # mode 0600, may be empty
/etc/hushmark/secrets/anthropic-api-key     # mode 0600, may be empty
/etc/hushmark/secrets/core-service-token    # mode 0600, required; at least 32 random characters
/srv/hushmark/models/hushmark-tr/           # immutable adopted model
```

The model directory must contain exactly the runtime artifact delivered after AC-1:

```text
gliner_config.json
model.onnx
tokenizer.json
tokenizer_config.json
```

`scripts/production/preflight.sh` verifies all four adopted checksums before Docker can start.

## Prepare without deploying

Clone the repository into `/opt/hushmark/repo` and check out the approved release ref. Create the host directories with root-only
permissions, copy `deploy/docker/production.env.example` to `/etc/hushmark/production.env`, and
replace the example domain. Store client/provider keys and the core service credential in the four
separate secret files; never
put them in the repository or Compose environment block. Generate a client key with at least 128
bits of randomness and the `hm_k1_` prefix.

Point the domain's A/AAAA record at the host before activation. Permit inbound TCP 80/443 and UDP
443; restrict SSH to operator addresses. Core and gateway publish no host ports.

Run the non-mutating gate:

```bash
cd /opt/hushmark/repo
sudo scripts/production/preflight.sh /etc/hushmark/production.env
```

This is the stopping point while no pilot exists. It validates the host, model, secrets, image
contract, and Compose rendering without pulling or starting containers.

## Activate for a pilot

After assigning an owner, approved data class, pilot end date, and rollback ref:

```bash
cd /opt/hushmark/repo
sudo scripts/production/deploy.sh /etc/hushmark/production.env
```

The script pulls the pinned images, waits for transitive readiness, runs an internal TCKN masking
smoke test without calling an upstream provider, and verifies the public HTTPS readiness endpoint.
Record the deployed Git commit and image digests in the pilot evidence.

## State, backup, and rollback

The community gateway vault is in-memory and intentionally loses placeholder mappings on restart.
The stack has no production database. Durable state is therefore limited to:

- the immutable model artifact, retained offline with its checksum evidence;
- the four secret values, retained in the operator's password manager; and
- Caddy certificate state, which is renewable and held in Docker named volumes.

Before an update, confirm the offline model artifact and password-manager entries are recoverable.
If the host uses a provider block volume, snapshot the non-secret data volume as an additional
recovery point. Do not copy plaintext secrets into a general-purpose backup archive.

Roll back without changing the repository worktree:

```bash
cd /opt/hushmark/repo
sudo scripts/production/rollback.sh <known-good-git-ref> /etc/hushmark/production.env
```

The rollback script exports only the production package from the selected commit into a temporary
directory, validates it, pulls its pinned images, replaces the running services, and checks HTTPS
readiness. If the host or volume is lost, recreate the host from this runbook, restore the verified
model directory and secret files, and deploy the recorded known-good ref.

## Operational limitations

This is a single-host pilot boundary, not high availability. Host maintenance causes downtime, the
in-memory vault is non-persistent, and a disk-backed model prevents transparent multi-instance
scaling. Move to a deliberately designed multi-host architecture only after measured demand
justifies the additional operational and privacy surface.
