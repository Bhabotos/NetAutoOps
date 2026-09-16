# NetAutoOps

A production-style Python Network Automation & Monitoring Platform. NetAutoOps manages network device inventory, monitors device health, collects interface information, performs configuration backups, exposes REST APIs, integrates with n8n, and sends alerts.

## Project Structure

```
NetAutoOps/
├── app/
│   ├── core/         # settings, database engine/session
│   ├── models/       # SQLAlchemy ORM models
│   ├── api/          # FastAPI routers and Pydantic schemas
│   ├── services/      # business logic, separate from HTTP layer
│   ├── monitoring/    # vendor adapters, reachability check, Netmiko client
│   ├── backup/        # structured backup file storage
│   ├── alerts/        # event schema, webhook client, n8n integration
│   └── utils/         # logging and shared helpers
├── tests/            # pytest test suite
├── config/
├── logs/
├── backups/
├── .env              # local secrets, never committed
├── .env.example      # documents required env vars (no real values)
├── .gitignore
├── Dockerfile         # multi-stage build, runs as non-root
├── docker-compose.yml # app + PostgreSQL for a fully containerized deployment
├── .dockerignore
├── README.md
└── requirements.txt
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this file). See `.env.example` for the full list of keys:

```
DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@localhost:5432/<db_name>
LOG_LEVEL=INFO

# Phase 3 monitoring (see below)
DEVICE_SSH_PASSWORD=
DEVICE_ENABLE_SECRET=
NETMIKO_TIMEOUT=10
TCP_CHECK_TIMEOUT=3

# Phase 4 configuration backups (reuses the credentials above)
BACKUP_COMMAND_TIMEOUT=60

# Phase 5 n8n webhook integration (empty = disabled, a safe no-op)
N8N_WEBHOOK_URL=
N8N_WEBHOOK_TIMEOUT=5
N8N_WEBHOOK_MAX_RETRIES=3
N8N_WEBHOOK_RETRY_BACKOFF_SECONDS=1
```

Run the API server:

```bash
uvicorn app.main:app --reload --port 8001
```

On startup the app automatically creates the `devices` table (and its enum types) in PostgreSQL if they don't already exist.

## Phase 2 — Device Inventory

Phase 2 adds a device inventory foundation backed by PostgreSQL.

### Device model

The `devices` table stores connection metadata for each network device:

| Field         | Type                          | Notes                                   |
|---------------|-------------------------------|------------------------------------------|
| id            | integer, primary key           | auto-increment                          |
| hostname      | string                          | required                                |
| ip_address    | string                          | required, **unique**, validated as IPv4/IPv6 |
| vendor        | string                          | required                                |
| device_type   | enum (router, switch, firewall, access_point, load_balancer, other) | required |
| username      | string                          | required (login username only)          |
| status        | enum (active, inactive, maintenance, unknown) | defaults to `unknown` |
| description   | string                          | optional                                |
| created_at    | timestamp                       | set automatically                       |
| updated_at    | timestamp                       | updated automatically on change         |

**Note on credentials:** device passwords are **not** stored in this table at all in this phase — only the login `username` is kept. Credential storage/retrieval (e.g. via a secrets vault or encrypted field) will be addressed when SSH-based automation (Netmiko) is introduced in a later phase.

### API Endpoints

| Method | Path             | Description                          |
|--------|------------------|---------------------------------------|
| POST   | `/devices`       | Create a new device                   |
| GET    | `/devices`       | List devices (supports `skip`/`limit`)|
| GET    | `/devices/{id}`  | Get a single device by id             |
| PUT    | `/devices/{id}`  | Partially update a device             |
| DELETE | `/devices/{id}`  | Delete a device                       |

Response codes: `201` on create, `200` on read/update, `204` on delete, `404` if a device id doesn't exist, `409` if the IP address already exists on another device, `422` on validation errors (e.g. invalid IP address).

### Example usage

```bash
curl -X POST http://127.0.0.1:8001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "core-router-01",
    "ip_address": "192.168.1.1",
    "vendor": "Cisco",
    "device_type": "router",
    "username": "admin",
    "status": "active",
    "description": "Core router in main lab"
  }'

curl http://127.0.0.1:8001/devices
curl http://127.0.0.1:8001/devices/1
curl -X PUT http://127.0.0.1:8001/devices/1 -H "Content-Type: application/json" -d '{"status": "maintenance"}'
curl -X DELETE http://127.0.0.1:8001/devices/1
```

### Logging

Application logs are written to both the console and `logs/netautoops.log`, including device create/update/delete events.

### Tests

Tests run against an isolated in-memory SQLite database (via a FastAPI dependency override) and never touch the real PostgreSQL database:

```bash
pytest tests/ -v
```

## Phase 3 — Device Health Monitoring (Netmiko)

Phase 3 adds read-only health monitoring of inventory devices over SSH using Netmiko.

**Safety rules enforced by design:** no configuration-changing commands are ever run (only `show`/`display` read-only commands), no credentials are hardcoded (SSH password/enable-secret come only from `.env`), and a failed or unreachable device check is caught and stored as a result — it never raises an exception into FastAPI.

### Architecture

```
app/monitoring/
├── reachability.py     # TCP-connect reachability + latency check (no ICMP, no root needed)
├── vendor_adapters.py  # per-vendor commands + output parsers behind one interface
└── netmiko_client.py   # opens a Netmiko session, runs read-only commands, maps exceptions

app/services/monitoring_service.py   # orchestrates the flow below and persists results
app/models/device_health.py          # `device_health` table (FK -> devices.id, ON DELETE CASCADE)
app/api/monitoring.py                # /monitoring/* endpoints
```

**Monitoring workflow** (`run_health_check`, one call per device):

1. Look up a vendor adapter for `device.vendor` (case-insensitive). Unknown vendor → `error` result, nothing else attempted.
2. TCP-connect to the device's IP on port 22 to record UP/DOWN and latency. This is a bare handshake — no data sent, no login. Unreachable → `down` result, Netmiko is never invoked.
3. Confirm `DEVICE_SSH_PASSWORD` is configured. Missing → `error` result explaining the missing env var.
4. Open a Netmiko session (read-only commands only) and run the adapter's `version`/`cpu`/`memory` commands. Any connection-level failure (auth, timeout, unexpected) → `error` result with a safe, hand-written message (never the raw exception text, so credentials can never leak into it).
5. A single command failing (e.g. unsupported syntax on a given firmware) doesn't abort the check — it's recorded per-command and the other metrics are still parsed and saved.
6. Parse `hostname`, `uptime`, `cpu_usage`, `memory_usage` from command output and persist one `device_health` row.

Every step is logged (monitoring started, device checked, successful collection, connection failure, command failure) without ever logging the password or secret.

### Supported platforms

The vendor-adapter pattern keeps the connect/collect/persist flow identical across vendors — only the Netmiko `device_type`, the three commands, and their output parsers differ:

| Vendor (case-insensitive) | Netmiko device_type | Commands used |
|---|---|---|
| Cisco  | `cisco_ios`  | `show version`, `show processes cpu \| include CPU utilization`, `show memory statistics \| include Processor` |
| Huawei | `huawei`     | `display version`, `display cpu-usage`, `display memory-usage` |
| Nokia  | `nokia_sros` | `show system information`, `show system cpu`, `show system memory` |

Any other vendor string (e.g. "Juniper") returns an `error` health result naming the unsupported vendor — it does not crash the request. Adding a new vendor means adding one `VendorAdapter` entry in `app/monitoring/vendor_adapters.py`; no other file changes.

> The regex-based parsers above are best-effort against typical CLI output and were validated against synthetic sample text in the test suite (see below), not a live device. Expect to adjust a regex for your specific firmware/software version the first time you point this at a real lab device.

### Monitoring database

New `device_health` table, one row per health check, linked to `devices` via `device_id` (`ON DELETE CASCADE` — deleting a device removes its history):

| Field | Type | Notes |
|---|---|---|
| id | integer, primary key | auto-increment |
| device_id | integer, FK → devices.id | required |
| status | enum (up, down, error) | |
| latency_ms | float | null if unreachable |
| hostname | string | parsed from device output, null on failure |
| uptime | string | parsed from device output, null on failure |
| cpu_usage | float | percent, null if unavailable |
| memory_usage | float | percent, null if unavailable |
| checked_at | timestamp | set automatically |
| error_message | string | null on a fully successful check |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/monitoring/devices/{device_id}` | Health check history for one device, most recent first (`skip`/`limit`) |
| POST | `/monitoring/devices/{device_id}/check` | Run a fresh check against the device right now |
| GET  | `/monitoring/health` | Latest known status for every device in the inventory |

All three return `404` if `device_id` doesn't exist in the inventory. `POST .../check` never returns a 5xx for a device-side failure (unreachable, auth failure, unsupported platform, etc.) — the failure is the `200`/`201` response body (`status: "down"` or `"error"` with `error_message` set).

### Example usage

```bash
# Run a check against device 1 (add it via /devices first)
curl -X POST http://127.0.0.1:8001/monitoring/devices/1/check

# History for device 1
curl http://127.0.0.1:8001/monitoring/devices/1

# Fleet-wide latest status
curl http://127.0.0.1:8001/monitoring/health
```

### Testing

`tests/test_monitoring.py` mocks Netmiko entirely (via `unittest.mock.patch` on `app.monitoring.netmiko_client.ConnectHandler`) — no test opens a real socket or SSH session except the standard-library reachability check, which is also monkeypatched in service/API-level tests. Covered:

- vendor adapter lookup (supported + unsupported platform) and output parsing for all three vendors, against synthetic sample CLI text
- Netmiko connection layer: success, authentication failure, timeout, and a single command failing without aborting the whole check
- orchestration service: full success path, unreachable device, unsupported platform, authentication failure, missing credentials, and an unexpected-exception path (proves a bug can't crash the API)
- API endpoints: `POST .../check`, `GET .../{id}` history, `GET /monitoring/health`, and 404s
- a `device_health` row is actually written to the database and readable back via the service/API

```bash
pytest tests/ -v
```

### Lab testing (GNS3 / EVE-NG)

No real network device was available in this environment, so Phase 3 was validated with Netmiko fully mocked, plus live end-to-end runs against safe non-device targets (an RFC 5737 `TEST-NET` address for the unreachable path, and an unsupported-vendor device for that path) — never against production infrastructure or real credentials.

To point this at a real lab device once one is available:

1. In GNS3 or EVE-NG, bring up a Cisco IOS(v)/IOU, Huawei VRP, or Nokia SR OS (VSR) node and give it a management interface reachable from this VM (e.g. bridged/NAT to a host-only network), with SSH enabled (`ip domain-name lab.local`, `crypto key generate rsa`, `line vty 0 4` / `transport input ssh`, a local user with SSH access).
2. Add its real management IP to `.env`'s reachability check target implicitly by registering it as a device (see step 3) — no IP goes into `.env`, only the shared SSH password does.
3. Set `DEVICE_SSH_PASSWORD` (and `DEVICE_ENABLE_SECRET` if the lab device requires enable mode) in `.env`.
4. Register the device:
   ```bash
   curl -X POST http://127.0.0.1:8001/devices -H "Content-Type: application/json" -d '{
     "hostname": "gns3-lab-router",
     "ip_address": "<lab device management IP>",
     "vendor": "Cisco",
     "device_type": "router",
     "username": "<ssh username configured on the lab device>",
     "status": "unknown"
   }'
   ```
5. Trigger a check and inspect the result:
   ```bash
   curl -X POST http://127.0.0.1:8001/monitoring/devices/<id>/check
   ```
6. If `cpu_usage`/`memory_usage` come back `null`, the regex in `app/monitoring/vendor_adapters.py` for that vendor's command output likely needs a small adjustment for your image/version — check `logs/netautoops.log` for the "Command failure" line naming which command failed, then compare against the raw output from running that same command manually over SSH.

## Phase 4 — Configuration Backup (Netmiko)

Phase 4 adds read-only configuration backups for inventory devices, built directly on the Phase 3 Netmiko foundation (same vendor-adapter pattern, same connection layer, same credential handling).

**Safety rules enforced by design:** only a single, pre-defined read-only command is ever run per vendor (`show running-config` / `display current-configuration` / `admin display-config` — none of these change device state), no credentials are hardcoded, and a failed backup (unreachable, auth failure, unsupported vendor, command failure, or file write failure) is caught and stored as a `failed` record — it never raises an exception into FastAPI, and no partial/corrupt file is left on disk.

### Architecture

Phase 4 reuses the Phase 3 building blocks rather than duplicating them:

```
app/monitoring/vendor_adapters.py   # extended: VendorAdapter now also carries `backup_command`
app/monitoring/netmiko_client.py    # extended: `fetch_running_config()` shares the same
                                     # `_open_connection()` helper (and exception mapping)
                                     # that Phase 3's collect_raw_outputs() uses
app/backup/storage.py               # NEW: structured backup file path + disk write
app/services/backup_service.py      # NEW: orchestrates fetch -> write -> persist
app/models/backup.py                # NEW: `device_backups` table (FK -> devices.id)
app/api/backups.py                  # NEW: /backups/* endpoints
```

**Backup workflow** (`run_backup`, one call per device):

1. Look up a vendor adapter for `device.vendor` (same lookup Phase 3 uses). Unknown vendor → `failed` record, nothing else attempted.
2. Confirm `DEVICE_SSH_PASSWORD` is configured. Missing → `failed` record explaining the missing env var.
3. Open a Netmiko session and run only the adapter's `backup_command`. A connection-level failure (auth, timeout, unexpected) or the command itself failing → `failed` record with a safe, hand-written message (never the raw exception text).
4. Only once the configuration text has been successfully retrieved does the code touch disk: compute the structured path, write the file, and record its size. If the write itself fails (e.g. disk full, permissions) → `failed` record; the device is never re-contacted to retry within the same call.
5. Persist one `device_backups` row either way.

Every step is logged (backup started, backup finished, unsupported vendor, connection/command failure, file write failure) without ever logging the password or secret.

### Supported platforms

Same three vendors as Phase 3, extended with one read-only backup command each:

| Vendor (case-insensitive) | Netmiko device_type | Backup command |
|---|---|---|
| Cisco  | `cisco_ios`  | `show running-config` |
| Huawei | `huawei`     | `display current-configuration` |
| Nokia  | `nokia_sros` | `admin display-config` (read-only despite the "admin" prefix — prints config, does not change it) |

Any other vendor string returns a `failed` result naming the unsupported vendor. Adding a new vendor means adding `backup_command` (and the existing monitoring fields) to one `VendorAdapter` entry — no other file changes.

### Backup directory structure

```
backups/
  <vendor>/
    <device_hostname>/
      <hostname>_<UTC timestamp>.cfg
```

Vendor and hostname are slugified (lowercased, unsafe characters replaced with `_`) before being used as directory/file names. Example: a Cisco device named `Lab Router 01` backed up produces `backups/cisco/lab_router_01/lab_router_01_20260916T223517Z.cfg`. `backups/` is git-ignored — backup content (potentially sensitive config) is never committed.

### Backup metadata database

New `device_backups` table, one row per backup attempt, linked to `devices` via `device_id` (`ON DELETE CASCADE`):

| Field | Type | Notes |
|---|---|---|
| id | integer, primary key | auto-increment |
| device_id | integer, FK → devices.id | required |
| filename | string | null if the backup failed before a file was written |
| file_path | string | path relative to the project root, null on failure |
| status | enum (success, failed) | |
| backup_size | integer (bytes) | null on failure |
| created_at | timestamp | set automatically |
| error_message | string | null on success |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/backups/devices/{device_id}` | Run a fresh configuration backup for the device right now |
| GET  | `/backups` | Every backup record across all devices, most recent first (`skip`/`limit`) |
| GET  | `/backups/devices/{device_id}` | Backup history for one device, most recent first |
| GET  | `/backups/{backup_id}` | A single backup record by id |

All endpoints return `404` if the referenced device/backup id doesn't exist. `POST .../devices/{id}` never returns a 5xx for a device-side failure — the failure is the `201` response body (`status: "failed"` with `error_message` set).

### Example usage

```bash
# Run a backup for device 1 (add it via /devices first)
curl -X POST http://127.0.0.1:8001/backups/devices/1

# All backups
curl http://127.0.0.1:8001/backups

# Backup history for device 1
curl http://127.0.0.1:8001/backups/devices/1

# A single backup record
curl http://127.0.0.1:8001/backups/1
```

### Testing

`tests/test_backup.py` mocks Netmiko entirely (same approach as Phase 3) plus tests the filesystem layer directly against `tmp_path`. Covered:

- storage layer: structured directory creation, filename slugification, file write + size reporting
- Netmiko backup fetch: success, authentication failure, timeout, and command failure (mocked `ConnectHandler`)
- orchestration service: full success path (mocked), a **real file actually written to a temp directory** (proves the storage integration, not just mocks), unsupported vendor, missing credentials, authentication failure, command failure, file write failure, and an unexpected-exception path
- database: backup rows created, listed, and fetched by id; a real cascade-delete-linked device
- API endpoints: `POST .../devices/{id}`, `GET /backups`, `GET .../devices/{id}`, `GET .../{id}`, and all 404s
- regression: `/`, `/health`, `/devices`, `/monitoring/health` all re-checked in the same file

```bash
pytest tests/ -v
```

### Lab testing (GNS3 / EVE-NG)

As with Phase 3, no real network device was available in this environment. The success path (an actual SSH session retrieving and saving a real running-config) is proven only via mocked Netmiko in the test suite — the failure paths (unsupported vendor, missing credentials) were additionally verified live against the real database using safe non-device targets, with zero files written to disk.

To back up a real lab device once one is available, reuse the same setup as Phase 3's lab testing section, then:

```bash
# 1. Register the device (see Phase 3 for the full device-registration example)
# 2. Make sure DEVICE_SSH_PASSWORD (and DEVICE_ENABLE_SECRET if needed) are set in .env
# 3. Run a backup:
curl -X POST http://127.0.0.1:8001/backups/devices/<id>

# 4. Inspect the result and the file it wrote:
curl http://127.0.0.1:8001/backups/devices/<id>
cat backups/cisco/<hostname>/<hostname>_<timestamp>.cfg
```

If the backup comes back `failed` with a command-related message, check `logs/netautoops.log` for the exact error, then try running the same `backup_command` manually over SSH to confirm the correct syntax for your device's firmware/software version.

## Phase 5 — n8n Integration

Phase 5 lets monitoring and backup events trigger external automation (Telegram, email, tickets, etc.) via n8n, without NetAutoOps knowing or caring what happens downstream — it only ever POSTs a standard JSON payload to one configured webhook URL.

**Safety rules enforced by design:** the webhook URL and every retry/timeout setting live only in `.env`; if `N8N_WEBHOOK_URL` is unset, event delivery is a logged no-op — nothing is ever sent anywhere by default; a webhook failure (timeout, connection error, 4xx/5xx, or anything unexpected) is caught and logged, never raised, so a broken or slow n8n instance can never crash or slow down a monitoring/backup API call; the webhook URL itself is treated like a credential and never appears unmasked in logs (n8n webhook paths embed an effectively-secret id).

### Architecture

```
app/alerts/events.py           # EventType enum + the standard EventPayload schema
app/alerts/webhook_client.py   # low-level HTTP POST: timeout, retry/backoff, error mapping
app/alerts/event_service.py    # public interface: dispatch_event() / deliver_event() -- never raises
app/api/events.py              # /events/* endpoints for discovery + manual testing
```

```
Device check (Phase 3) ──┐
Backup run (Phase 4)   ──┼──> event_service.dispatch_event() ──> webhook_client.send_webhook() ──> n8n
                          │         (never raises)                 (timeout + retry + 4xx/5xx handling)
POST /events/test        ─┘
```

`monitoring_service.py` and `backup_service.py` call `event_service.dispatch_event(...)` at the same points they already persist a result — no new code path, no chance of an event firing without a corresponding database record (or vice versa).

### Standard events

| Event | Fired when | Source |
|---|---|---|
| `device_down` | A health check finds the device unreachable | every occurrence, Phase 3 |
| `device_recovered` | A health check succeeds (`UP`) immediately after a `DOWN`/`ERROR` check | only on the transition, Phase 3 |
| `health_check_failed` | A health check errors out (unsupported platform, missing credentials, auth/timeout/unexpected failure) | every occurrence, Phase 3 |
| `backup_success` | A configuration backup completes and the file is written | every occurrence, Phase 4 |
| `backup_failed` | A configuration backup fails for any reason | every occurrence, Phase 4 |

`device_recovered` is transition-only so a consistently healthy device doesn't fire an event on every routine check; the other four fire every time so an n8n workflow can decide for itself whether to de-duplicate/rate-limit.

### Event payload

Every event, regardless of source, has this shape (`details` carries event-specific extras):

```json
{
  "event": "device_down",
  "device_id": 1,
  "hostname": "R1",
  "ip_address": "192.168.1.10",
  "status": "down",
  "timestamp": "2026-09-16T23:05:00.123456+00:00",
  "details": {
    "error_message": "Device did not respond on the management port (TCP/22)",
    "latency_ms": null
  }
}
```

`details` per event: `device_down`/`health_check_failed` carry `error_message` (+`latency_ms` for `device_down`); `device_recovered` carries `cpu_usage`/`memory_usage`; `backup_success` carries `filename`/`backup_size`; `backup_failed` carries `error_message`. `details` is always present as a key (possibly `null`), so an n8n node can safely reference `{{$json.details}}` without an existence check.

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/events/types` | The five event names above, for building an n8n IF/Switch node |
| POST | `/events/test` | Build and send one event for an existing device, and return whether it was delivered |

`POST /events/test` body: `{"event": "device_down", "device_id": 1, "status": "down", "details": {...}}` (`status` and `details` optional). It never touches the monitoring/backup tables — it's purely for verifying the webhook path (payload shape, n8n reachability, retry behavior) end to end.

### Testing

`tests/test_events.py` mocks `httpx.post` (never opens a real socket) plus a `conftest.py` fixture that skips retry sleeps so slow tests don't accumulate. Covered:

- event schema: standard payload shape, `details` passthrough, and Pydantic validation rejecting missing fields / an unknown event name
- webhook client: successful delivery, URL-not-configured (no request attempted), timeout (retries then fails), connection failure (retries then fails), a transient timeout followed by success, HTTP 4xx (fails immediately, no retry), HTTP 5xx (retries then fails), and a response whose body can't be read (doesn't crash the error path)
- a dedicated test asserting the webhook URL never appears unmasked in the logs
- event service: `deliver_event`/`dispatch_event` never raise and return the correct bool in every case above
- integration: monitoring dispatches `device_down`/`health_check_failed`/`device_recovered` at the right transitions and stays silent on consecutive healthy checks; backup dispatches `backup_success`/`backup_failed`
- API endpoints: `/events/types`, `/events/test` (delivered, not-configured, 404, invalid event name)
- regression: `/`, `/health`, `/devices`, `/monitoring/health`, `/backups` all re-checked in the same file

```bash
pytest tests/ -v
```

Live end-to-end verification performed for this phase (see the session's implementation, not part of the automated suite): a real `http.server`-based receiver on `127.0.0.1` confirmed an actual `httpx` POST is correctly delivered outside of mocks, and `POST /events/test` against the real database correctly returned `delivered: false` with no outbound attempt when `N8N_WEBHOOK_URL` was unset.

### Testing with local n8n

You don't need Docker or a public server to try this end-to-end:

1. **Get n8n running somewhere reachable from this machine.** The quickest options: [n8n cloud](https://n8n.io) free trial, or n8n desktop. (This step is entirely your own n8n instance — NetAutoOps doesn't deploy or manage it.)
2. **Create a workflow**: `Webhook` node (Production URL, POST) → `IF`/`Switch` node branching on `{{$json.event}}` → a `Telegram` or `Email` node on whichever branches you want notified (per the task, these aren't required yet — a `NoOp` or `Set` node is enough to prove the pipeline).
3. Copy the webhook's **Production URL** into `.env`:
   ```
   N8N_WEBHOOK_URL=https://<your-n8n-host>/webhook/<your-webhook-id>
   ```
4. Restart NetAutoOps (or just re-trigger — `uvicorn --reload` picks up `.env` changes on restart) and send a test event:
   ```bash
   curl -X POST http://127.0.0.1:8001/events/test \
     -H "Content-Type: application/json" \
     -d '{"event": "device_down", "device_id": 1, "status": "down"}'
   ```
5. Check the n8n workflow's execution log — you should see the exact payload from the "Event payload" section above.
6. Once that works, trigger it for real: `POST /monitoring/devices/1/check` against an unreachable device, or `POST /backups/devices/1` against an unsupported vendor, and watch the same event arrive from the real monitoring/backup flow instead of the test endpoint.

If you don't want to set up n8n yet, use [webhook.site](https://webhook.site) instead — it hands you a disposable URL and shows every request it receives, which is enough to confirm NetAutoOps is sending the right payload before you build the n8n workflow. (The payload contains only inventory metadata — hostname, IP, status — never credentials, so this is safe to point at a public tool.)

### n8n workflow diagram

```
NetAutoOps (monitoring/backup service)
   ↓  POST JSON (see "Event payload" above)
Webhook node (n8n)
   ↓
IF / Switch node on {{$json.event}}
   ↓                    ↓                        ↓
device_down /     backup_success /        (any other event)
health_check_failed   backup_failed
   ↓                    ↓
Telegram or Email    Telegram or Email    (log / ignore for now)
```

## Phase 6 — Docker Deployment

Phase 6 packages NetAutoOps into a container and adds a `docker compose` stack (app + PostgreSQL) for a fully self-contained deployment, alongside the existing host-based (`uvicorn` directly) workflow -- both continue to work side by side using the same `.env`.

**Safety note:** this phase is pure infrastructure -- containerizing the app changes nothing about how it talks to network devices (still read-only Netmiko commands, still no credentials in code, still `DEVICE_SSH_PASSWORD`/`N8N_WEBHOOK_URL` from the environment only). No device is contacted differently because it's running in a container.

### Image

`Dockerfile` is a multi-stage build:

1. **builder** stage: installs `requirements.txt` into an isolated user site-packages directory (nothing here ends up in the final image except the installed packages).
2. **runtime** stage: `python:3.14-slim` (Debian-based -- `psycopg2-binary`'s prebuilt wheel needs glibc, so this intentionally isn't an Alpine/musl image), copies in the installed packages and `app/` only (no tests, no `.git`, no `.env` -- see `.dockerignore`), creates and switches to a non-root `appuser`, and runs `uvicorn` on port 8001.

A `HEALTHCHECK` hits `/health` every 30s so `docker ps` and `depends_on: condition: service_healthy` can see real application health, not just "the process is running."

### Running with docker compose

`docker-compose.yml` defines two services:

| Service | Image | Notes |
|---|---|---|
| `db` | `postgres:18-alpine` | Named volume `postgres_data` for persistence; `pg_isready` healthcheck gates the app's startup |
| `app` | built from `Dockerfile` | Loads `.env` for every setting except `DATABASE_URL`, which compose overrides to point at `db:5432` instead of `localhost` (the app container can't reach the host's own PostgreSQL via "localhost" -- that would mean itself) |

`./logs` and `./backups` are bind-mounted into the container at the same paths the app already uses, so log files and configuration backups land directly in your project directory exactly as they do when running via `uvicorn` on the host -- nothing extra to `docker cp` out.

**Setup:**

1. Add three new keys to `.env` (see `.env.example`) -- these initialize the *containerized* PostgreSQL and are separate from the `DATABASE_URL` used for host-based `uvicorn` runs:
   ```
   POSTGRES_USER=netautoops_user
   POSTGRES_PASSWORD=<choose a password>
   POSTGRES_DB=netautoops_db
   ```
2. Build and start:
   ```bash
   docker compose up -d --build
   ```
3. Check both containers are healthy:
   ```bash
   docker compose ps
   ```
4. Verify:
   ```bash
   curl http://127.0.0.1:8001/health
   curl http://127.0.0.1:8001/devices
   ```
5. Logs:
   ```bash
   docker compose logs -f app
   # or, since it's bind-mounted:
   tail -f logs/netautoops.log
   ```
6. Stop (keeps the database volume): `docker compose down`. Stop and wipe the database too: `docker compose down -v`.

> If you already have PostgreSQL running natively on the host (as set up in Phase 2) and only want to containerize the *app*, run `docker build -t netautoops .` and `docker run` it directly with `DATABASE_URL` pointing at `host.docker.internal` (Docker Desktop) or the host's real IP (Linux) instead of using `docker-compose.yml`'s bundled database.

### What was verified in this environment

Both containers were built and run end-to-end here: `db` passed its `pg_isready` healthcheck, `app` connected to it, created all tables, and passed its own `/health` healthcheck. Every existing endpoint was re-verified against the containerized stack -- Phase 2 device CRUD, Phase 3 monitoring check + fleet health, Phase 4 backup trigger + list, Phase 5 event types -- all returned the expected status codes. Data survived a full container restart (named volume persistence confirmed), and the `logs`/`backups` bind mounts were confirmed to receive real writes from inside the container. The test-only stack was torn down afterward (`down -v`) and never left running.

### requirements.txt

No changes -- the same dependency set that runs on the host runs unchanged in the container (verified: `psycopg2-binary`'s wheel installs cleanly on `python:3.14-slim` with no extra system packages needed).

## Health Check

```bash
curl http://127.0.0.1:8001/health
```
