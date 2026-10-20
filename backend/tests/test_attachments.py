from sqlalchemy import func, select

from app.core.config import settings
from app.models.attachment import Attachment
from tests.conftest import auth_headers, register_and_login


def _flight(client, headers):
    response = client.post(
        "/api/v1/flights",
        json={"origin": "HKG", "destination": "NRT", "service_number": "CX524"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(
    client, headers, resource_type, resource_id, name="boarding-pass.pdf", data=b"%PDF-1.4 test"
):
    return client.post(
        "/api/v1/attachments",
        data={"resource_type": resource_type, "resource_id": resource_id},
        files={"file": (name, data, "application/pdf")},
        headers=headers,
    )


def test_upload_list_download_and_delete_attachment(client, storage):
    token = register_and_login(client, "attach_crud")["access_token"]
    headers = auth_headers(token)
    flight = _flight(client, headers)

    response = _upload(client, headers, "flight", flight["id"])
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert attachment["filename"] == "boarding-pass.pdf"
    assert attachment["mime_type"] == "application/pdf"
    assert attachment["size"] == len(b"%PDF-1.4 test")
    assert "storage_key" not in attachment
    assert len(storage.objects) == 1
    key = next(iter(storage.objects))
    assert key.startswith(f"users/{flight['user_id']}/attachments/")
    assert str(flight["id"]) not in key

    response = client.get(
        "/api/v1/attachments",
        params={"resource_type": "flight", "resource_id": flight["id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == attachment["id"]

    response = client.get(f"/api/v1/attachments/{attachment['id']}/download", headers=headers)
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 test"
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment;" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"

    response = client.delete(f"/api/v1/attachments/{attachment['id']}", headers=headers)
    assert response.status_code == 204
    assert storage.objects == {}
    assert (
        client.get(
            "/api/v1/attachments",
            params={"resource_type": "flight", "resource_id": flight["id"]},
            headers=headers,
        ).json()["total"]
        == 0
    )
    assert (
        client.get(f"/api/v1/attachments/{attachment['id']}/download", headers=headers).status_code
        == 404
    )


def test_attachment_routes_are_user_scoped(client, storage):
    owner = register_and_login(client, "attach_owner")["access_token"]
    intruder = register_and_login(client, "attach_intruder")["access_token"]
    owner_headers = auth_headers(owner)
    intruder_headers = auth_headers(intruder)

    flight = _flight(client, owner_headers)
    uploaded = _upload(client, owner_headers, "flight", flight["id"])
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["id"]

    assert _upload(client, intruder_headers, "flight", flight["id"]).status_code == 404
    assert (
        client.get(
            "/api/v1/attachments",
            params={"resource_type": "flight", "resource_id": flight["id"]},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/attachments/{attachment_id}/download", headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/attachments/{attachment_id}", headers=intruder_headers).status_code
        == 404
    )
    assert len(storage.objects) == 1


def test_attachment_validation(client):
    token = register_and_login(client, "attach_invalid")["access_token"]
    headers = auth_headers(token)
    flight = _flight(client, headers)

    response = _upload(client, headers, "hotel", flight["id"])
    assert response.status_code == 400

    response = _upload(client, headers, "train", flight["id"])
    assert response.status_code == 404

    response = client.post(
        "/api/v1/attachments",
        data={"resource_type": "flight", "resource_id": flight["id"]},
        files={"file": ("ticket.html", b"<script>alert(1)</script>", "text/html")},
        headers=headers,
    )
    assert response.status_code == 415

    response = client.post(
        "/api/v1/attachments",
        data={"resource_type": "flight", "resource_id": flight["id"]},
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 422


def test_attachment_size_limit_and_filename_sanitizing(client, monkeypatch):
    token = register_and_login(client, "attach_size")["access_token"]
    headers = auth_headers(token)
    flight = _flight(client, headers)

    response = client.post(
        "/api/v1/attachments",
        data={"resource_type": "flight", "resource_id": flight["id"]},
        files={"file": ("../../evil.png", b"png-bytes", "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "evil.png"
    assert body["mime_type"] == "image/png"

    monkeypatch.setattr(settings, "max_attachment_bytes", 4)
    response = _upload(client, headers, "flight", flight["id"], name="big.pdf", data=b"12345")
    assert response.status_code == 413


def test_train_and_transport_attachments(client):
    token = register_and_login(client, "attach_types")["access_token"]
    headers = auth_headers(token)

    train = client.post(
        "/api/v1/trains",
        json={"origin": "HKG", "destination": "SHA", "service_number": "G100"},
        headers=headers,
    )
    assert train.status_code == 201, train.text
    assert _upload(client, headers, "train", train.json()["id"]).status_code == 201

    transport = client.post(
        "/api/v1/other-transports",
        json={"origin": "HKG", "destination": "Macau", "vehicle_type": "bus"},
        headers=headers,
    )
    assert transport.status_code == 201, transport.text
    assert _upload(client, headers, "transport", transport.json()["id"]).status_code == 201


def test_deleting_a_record_removes_its_attachments(client, db, storage):
    token = register_and_login(client, "attach_record_delete")["access_token"]
    headers = auth_headers(token)
    flight = _flight(client, headers)
    assert _upload(client, headers, "flight", flight["id"]).status_code == 201
    assert len(storage.objects) == 1

    response = client.delete(f"/api/v1/flights/{flight['id']}", headers=headers)
    assert response.status_code == 204
    assert storage.objects == {}
    assert db.scalar(select(func.count()).select_from(Attachment)) == 0


def test_deleting_an_account_removes_attachments(client, db, storage):
    token = register_and_login(client, "attach_account_delete")["access_token"]
    headers = auth_headers(token)
    flight = _flight(client, headers)
    assert _upload(client, headers, "flight", flight["id"]).status_code == 201

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "secret123"}, headers=headers
    )
    assert response.status_code == 204, response.text
    assert storage.objects == {}
    assert db.scalar(select(func.count()).select_from(Attachment)) == 0
