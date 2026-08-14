# SZYG Control Plane

Cloud control plane for private beta user provisioning, device authorization,
entitlements, usage accounting, feedback and provider-neutral model routing.

## Local development

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 18080
```

SQLite is used when `CONTROL_DATABASE_URL` is omitted. Production must use
PostgreSQL and a 32+ character JWT secret.

## Dolphin deployment

1. Copy `.env.example` to `.env` and fill secrets on the server only.
2. Create `secrets/postgres_password.txt` with mode `600`.
3. Generate the offline-license signing keys:

```bash
mkdir -p secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
  -out secrets/offline_license_private.pem
openssl rsa -pubout -in secrets/offline_license_private.pem \
  -out secrets/offline_license_public.pem
chmod 600 secrets/postgres_password.txt secrets/offline_license_private.pem
chmod 644 secrets/offline_license_public.pem
```

4. Run `docker compose up -d postgres control-api control-worker`.
5. Validate through `ssh -L 18080:127.0.0.1:18080 dolphin`. Port `18080`
   must remain bound to `127.0.0.1` and must not be opened in the cloud firewall.
6. After DNS is ready, set `CONTROL_DOMAIN` and run
   `docker compose --profile public up -d` to expose the service through Caddy on
   HTTPS only.
7. Install `scripts/backup.sh` as a daily job and perform a restore test before
   inviting external beta users.

The desktop app stores only a DPAPI-encrypted refresh token and a signed offline
license. Provider credentials and real model identifiers stay on the server.

Never add `.env`, `secrets/` or database backups to Git.

## Usage and billing reconciliation

Successful inference calls are settled from the usage returned by the provider.
The user-facing daily Credits total uses the Asia/Shanghai calendar day. Failed
calls are not charged, and asynchronous video calls settle only after completion.

For delayed provider-bill reconciliation, create a dedicated read-only IAM user
with billing read access and set `CONTROL_PROVIDER_BILLING_ACCESS_KEY` and
`CONTROL_PROVIDER_BILLING_SECRET_KEY` on the server. The worker refreshes the
current and previous three billing days. These credentials must never be reused
as inference credentials or copied into the desktop package.

Set `CONTROL_PROVIDER_BILLING_PROJECT` to the dedicated VolcEngine project used
by SZYG. Without this filter, other Ark usage under the same payer account may be
included in the reconciliation total. A daily API cost share above 65% or a
provider-bill variance above 5% is emitted as an operator alert.
