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
│   ├── monitoring/    # (future phase)
│   ├── backup/        # (future phase)
│   ├── alerts/        # (future phase)
│   └── utils/         # logging and shared helpers
├── tests/            # pytest test suite
├── config/
├── logs/
├── backups/
├── .env              # local secrets, never committed
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

Create a `.env` file in the project root (never commit this file):

```
DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@localhost:5432/<db_name>
LOG_LEVEL=INFO
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

## Health Check

```bash
curl http://127.0.0.1:8001/health
```
