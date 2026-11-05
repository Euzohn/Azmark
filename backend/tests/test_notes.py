"""Note CRUD, search and user isolation (spec #21, #57)."""

from sqlalchemy import select

from app.models.note import Note
from tests.conftest import auth_headers, register_and_login

NOTE = {
    "title": "Singapore packing list",
    "content": "Passport, adapters, sunscreen",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def test_create_and_read_note(client):
    headers = _headers(client, "note_create")
    resp = client.post("/api/v1/notes", json=NOTE, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == NOTE["title"]
    assert body["content"] == NOTE["content"]

    got = client.get(f"/api/v1/notes/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["title"] == NOTE["title"]


def test_title_is_required(client):
    headers = _headers(client, "note_required")
    assert client.post("/api/v1/notes", json={"content": "x"}, headers=headers).status_code == 422
    empty_title = client.post("/api/v1/notes", json={"title": "", "content": "x"}, headers=headers)
    assert empty_title.status_code == 422


def test_list_and_search(client):
    headers = _headers(client, "note_list")
    client.post("/api/v1/notes", json=NOTE, headers=headers)
    client.post(
        "/api/v1/notes",
        json={"title": "Tokyo food plan", "content": "Tsukiji, ramen"},
        headers=headers,
    )
    assert client.get("/api/v1/notes", headers=headers).json()["total"] == 2

    by_title = client.get("/api/v1/notes", params={"search": "tokyo"}, headers=headers).json()
    assert by_title["total"] == 1
    assert by_title["items"][0]["title"] == "Tokyo food plan"

    by_content = client.get("/api/v1/notes", params={"search": "passport"}, headers=headers).json()
    assert by_content["total"] == 1
    assert by_content["items"][0]["title"] == NOTE["title"]


def test_update_note(client):
    headers = _headers(client, "note_update")
    created = client.post("/api/v1/notes", json=NOTE, headers=headers).json()
    resp = client.patch(
        f"/api/v1/notes/{created['id']}",
        json={"title": "Updated", "content": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Updated"
    assert resp.json()["content"] is None


def test_explicit_null_does_not_wipe_title(client):
    headers = _headers(client, "note_null")
    created = client.post("/api/v1/notes", json=NOTE, headers=headers).json()
    resp = client.patch(
        f"/api/v1/notes/{created['id']}",
        json={"title": None, "content": "changed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == NOTE["title"]
    assert resp.json()["content"] == "changed"


def test_delete_note(client, db):
    headers = _headers(client, "note_delete")
    created = client.post("/api/v1/notes", json=NOTE, headers=headers).json()
    assert client.delete(f"/api/v1/notes/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/notes/{created['id']}", headers=headers).status_code == 404
    assert db.scalar(select(Note)) is None


def test_user_isolation(client):
    a = _headers(client, "note_iso_a")
    b = _headers(client, "note_iso_b")
    created = client.post("/api/v1/notes", json=NOTE, headers=a).json()
    assert client.get(f"/api/v1/notes/{created['id']}", headers=b).status_code == 404
    assert (
        client.patch(f"/api/v1/notes/{created['id']}", json={"title": "x"}, headers=b).status_code
        == 404
    )
    assert client.delete(f"/api/v1/notes/{created['id']}", headers=b).status_code == 404
    assert client.get("/api/v1/notes", headers=b).json()["total"] == 0


def test_trip_assignment_and_foreign_trip_rejected(client):
    a = _headers(client, "note_trip_a")
    b = _headers(client, "note_trip_b")
    trip = client.post("/api/v1/trips", json={"name": "Tokyo 2026"}, headers=a).json()
    linked = client.post("/api/v1/notes", json={**NOTE, "trip_id": trip["id"]}, headers=a)
    assert linked.status_code == 201, linked.text
    assert linked.json()["trip_id"] == trip["id"]

    per_trip = client.get("/api/v1/notes", params={"trip_id": trip["id"]}, headers=a).json()
    assert per_trip["total"] == 1

    foreign = client.post("/api/v1/notes", json={**NOTE, "trip_id": trip["id"]}, headers=b)
    assert foreign.status_code == 404


def test_audit_log(client):
    headers = _headers(client, "note_audit")
    created = client.post("/api/v1/notes", json=NOTE, headers=headers).json()
    client.patch(f"/api/v1/notes/{created['id']}", json={"title": "x"}, headers=headers)
    entries = client.get("/api/v1/audit-logs", headers=headers).json()["items"]
    actions = {e["action"] for e in entries if e["resource_type"] == "note"}
    assert "create_record" in actions
    assert "update_record" in actions
