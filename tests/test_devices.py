def sample_device(ip="10.0.0.1", hostname="core-sw-01"):
    return {
        "hostname": hostname,
        "ip_address": ip,
        "vendor": "Cisco",
        "device_type": "switch",
        "username": "admin",
        "status": "active",
        "description": "Core switch in lab rack 1",
    }


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_device(client):
    response = client.post("/devices", json=sample_device())
    assert response.status_code == 201
    data = response.json()
    assert data["hostname"] == "core-sw-01"
    assert data["ip_address"] == "10.0.0.1"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data


def test_create_device_invalid_ip(client):
    payload = sample_device(ip="not-an-ip")
    response = client.post("/devices", json=payload)
    assert response.status_code == 422


def test_create_device_duplicate_ip(client):
    client.post("/devices", json=sample_device(ip="10.0.0.5", hostname="sw-a"))
    response = client.post("/devices", json=sample_device(ip="10.0.0.5", hostname="sw-b"))
    assert response.status_code == 409


def test_list_devices(client):
    client.post("/devices", json=sample_device(ip="10.0.0.10", hostname="sw-1"))
    client.post("/devices", json=sample_device(ip="10.0.0.11", hostname="sw-2"))
    response = client.get("/devices")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_device_by_id(client):
    created = client.post("/devices", json=sample_device(ip="10.0.0.20")).json()
    response = client.get(f"/devices/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_device_not_found(client):
    response = client.get("/devices/9999")
    assert response.status_code == 404


def test_update_device(client):
    created = client.post("/devices", json=sample_device(ip="10.0.0.30")).json()
    response = client.put(
        f"/devices/{created['id']}",
        json={"status": "maintenance", "description": "Undergoing firmware upgrade"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "maintenance"
    assert data["description"] == "Undergoing firmware upgrade"
    assert data["hostname"] == created["hostname"]


def test_update_device_duplicate_ip(client):
    first = client.post("/devices", json=sample_device(ip="10.0.0.40", hostname="sw-a")).json()
    client.post("/devices", json=sample_device(ip="10.0.0.41", hostname="sw-b"))
    response = client.put(f"/devices/{first['id']}", json={"ip_address": "10.0.0.41"})
    assert response.status_code == 409


def test_update_device_not_found(client):
    response = client.put("/devices/9999", json={"status": "active"})
    assert response.status_code == 404


def test_delete_device(client):
    created = client.post("/devices", json=sample_device(ip="10.0.0.50")).json()
    response = client.delete(f"/devices/{created['id']}")
    assert response.status_code == 204
    response = client.get(f"/devices/{created['id']}")
    assert response.status_code == 404


def test_delete_device_not_found(client):
    response = client.delete("/devices/9999")
    assert response.status_code == 404
