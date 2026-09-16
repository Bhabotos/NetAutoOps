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
│   ├── backup/        # (future phase)
│   ├── alerts/        # (future phase)
│   └── utils/         # logging and shared helpers
├── tests/            # pytest test suite
├── config/
├── logs/
├── backups/
├── .env              # local secrets, never committed
├── .env.example      # documents required env vars (no real values)
├── .gitignore
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

## Health Check

```bash
curl http://127.0.0.1:8001/health
```
