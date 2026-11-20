"""Photo organization: deterministic trip suggestions and confirmed batches."""

import asyncio
import uuid

from sqlalchemy import select

from app.models.audit_log import AuditAction, AuditLog
from app.services.ai_tools import TOOLS
from tests.conftest import auth_headers, register_and_login
from tests.test_pending_actions import _confirm, _make_write_token, _mcp_call
from tests.test_photos import _jpeg, _upload


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _trip(client, headers, name: str = "SG 2026", **dates) -> dict:
    response = client.post("/api/v1/trips", json={"name": name, **dates}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _hotel_in_trip(client, headers, trip_id: str, lat=1.2839, lon=103.8607) -> dict:
    response = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Marina Bay Sands",
            "check_in": "2026-04-29",
            "trip_id": trip_id,
            "lat": lat,
            "lon": lon,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _suggestions(client, headers) -> dict:
    response = client.get("/api/v1/photos/suggestions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_time_match_suggests_trip(client):
    headers = _headers(client, "org_time")
    trip = _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    photo = _upload(client, headers, _jpeg(exif=True)).json()

    body = _suggestions(client, headers)
    assert body["unassigned_total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["photo"]["id"] == photo["id"]
    assert "storage_key" not in item["photo"]
    assert len(item["candidates"]) == 1
    candidate = item["candidates"][0]
    assert candidate["trip_id"] == trip["id"]
    assert candidate["reasons"] == ["time"]
    assert candidate["confidence"] == "medium"
    assert candidate["distance_km"] is None


def test_geo_match_uses_hotels_and_activity_places(client):
    headers = _headers(client, "org_geo")
    trip_hotel = _trip(client, headers, name="Hotel trip")
    _hotel_in_trip(client, headers, trip_hotel["id"])
    trip_place = _trip(client, headers, name="Place trip")
    place = client.post(
        "/api/v1/places",
        json={"name": "Gardens by the Bay", "type": "attraction", "lat": 1.2816, "lon": 103.8636},
        headers=headers,
    )
    assert place.status_code == 201, place.text
    activity = client.post(
        "/api/v1/activities",
        json={
            "name": "Evening walk",
            "type": "other",
            "place_id": place.json()["id"],
            "trip_id": trip_place["id"],
        },
        headers=headers,
    )
    assert activity.status_code == 201, activity.text
    _upload(client, headers, _jpeg(exif=True))

    item = _suggestions(client, headers)["items"][0]
    assert {c["trip_id"] for c in item["candidates"]} == {trip_hotel["id"], trip_place["id"]}
    for candidate in item["candidates"]:
        assert candidate["reasons"] == ["geo"]
        assert candidate["confidence"] == "weak"
        assert candidate["distance_km"] is not None
        assert candidate["distance_km"] < 50


def test_time_and_geo_match_is_strong(client):
    headers = _headers(client, "org_strong")
    trip = _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    _hotel_in_trip(client, headers, trip["id"])
    _upload(client, headers, _jpeg(exif=True))

    candidate = _suggestions(client, headers)["items"][0]["candidates"][0]
    assert candidate["reasons"] == ["time", "geo"]
    assert candidate["confidence"] == "strong"


def test_candidates_ranked_by_confidence(client):
    headers = _headers(client, "org_rank")
    dates = {"start_date": "2026-04-28", "end_date": "2026-05-05"}
    strong = _trip(client, headers, name="Strong trip", **dates)
    _hotel_in_trip(client, headers, strong["id"])
    weak = _trip(client, headers, name="Time only trip", **dates)
    _upload(client, headers, _jpeg(exif=True))

    candidates = _suggestions(client, headers)["items"][0]["candidates"]
    assert [c["trip_id"] for c in candidates] == [strong["id"], weak["id"]]
    assert [c["confidence"] for c in candidates] == ["strong", "medium"]


def test_photo_without_exif_or_gps_is_counted_but_not_suggested(client):
    headers = _headers(client, "org_plain")
    _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    _upload(client, headers, _jpeg(), name="plain.jpg")
    _upload(client, headers, _jpeg(exif=True), name="gps.jpg")

    body = _suggestions(client, headers)
    assert body["unassigned_total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["photo"]["filename"] == "gps.jpg"


def test_filed_photos_are_not_suggested(client):
    headers = _headers(client, "org_filed")
    trip = _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    _upload(client, headers, _jpeg(exif=True), trip_id=trip["id"])

    body = _suggestions(client, headers)
    assert body["items"] == []
    assert body["unassigned_total"] == 0


def test_suggestions_are_user_scoped(client):
    owner = _headers(client, "org_owner")
    _trip(client, owner, start_date="2026-04-28", end_date="2026-05-05")
    _upload(client, owner, _jpeg(exif=True))

    intruder = _headers(client, "org_intruder")
    body = _suggestions(client, intruder)
    assert body["items"] == []
    assert body["unassigned_total"] == 0


def test_organize_applies_batch_and_audits(client, db):
    headers = _headers(client, "org_apply")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    trip = _trip(client, headers)
    first = _upload(client, headers, _jpeg(exif=True), name="a.jpg").json()
    second = _upload(client, headers, _jpeg(), name="b.jpg").json()

    response = client.post(
        "/api/v1/photos/organize",
        json={
            "assignments": [
                {"photo_id": first["id"], "trip_id": trip["id"]},
                {"photo_id": second["id"], "trip_id": trip["id"]},
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"updated": 2}

    filed = client.get(f"/api/v1/photos?trip_id={trip['id']}", headers=headers).json()
    assert {p["id"] for p in filed["items"]} == {first["id"], second["id"]}
    assert _suggestions(client, headers)["unassigned_total"] == 0

    logs = db.scalars(
        select(AuditLog).where(
            AuditLog.user_id == uuid.UUID(me["id"]),
            AuditLog.action == AuditAction.UPDATE_RECORD,
            AuditLog.resource_type == "photo",
        )
    ).all()
    assert any(log.meta.get("organized_count") == 2 for log in logs)


def test_organize_is_all_or_nothing_on_foreign_ids(client):
    owner = _headers(client, "org_batch_owner")
    trip = _trip(client, owner)
    photo = _upload(client, owner, _jpeg(exif=True)).json()
    intruder = _headers(client, "org_batch_intruder")
    foreign_trip = _trip(client, intruder, name="Not yours")
    foreign_photo = _upload(client, intruder, _jpeg(), name="theirs.jpg").json()

    # A foreign trip in the batch rejects everything; nothing is filed.
    response = client.post(
        "/api/v1/photos/organize",
        json={
            "assignments": [
                {"photo_id": photo["id"], "trip_id": trip["id"]},
                {"photo_id": photo["id"], "trip_id": foreign_trip["id"]},
            ]
        },
        headers=owner,
    )
    assert response.status_code == 404
    assert client.get(f"/api/v1/photos/{photo['id']}", headers=owner).json()["trip_id"] is None

    # A foreign photo is indistinguishable from a missing one.
    response = client.post(
        "/api/v1/photos/organize",
        json={"assignments": [{"photo_id": foreign_photo["id"], "trip_id": trip["id"]}]},
        headers=owner,
    )
    assert response.status_code == 404


def test_organize_validation_and_auth(client):
    # Before any login: the test client keeps cookies, so check auth first.
    assert client.post("/api/v1/photos/organize", json={"assignments": []}).status_code == 401
    assert client.get("/api/v1/photos/suggestions").status_code == 401
    headers = _headers(client, "org_validate")
    assert (
        client.post(
            "/api/v1/photos/organize", json={"assignments": []}, headers=headers
        ).status_code
        == 422
    )


def test_suggestions_capped_to_organize_batch_limit(client, monkeypatch):
    from app.services import photo_organization

    headers = _headers(client, "org_cap")
    _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    for index in range(3):
        _upload(client, headers, _jpeg(exif=True), name=f"p{index}.jpg")
    monkeypatch.setattr(photo_organization, "MAX_SUGGESTIONS", 2)

    body = _suggestions(client, headers)
    assert body["unassigned_total"] == 3
    assert len(body["items"]) == 2


def _user_id(client, headers) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["id"])


def test_ai_suggest_tool_returns_facts_only(client, db):
    headers = _headers(client, "org_ai_read")
    trip = _trip(client, headers, start_date="2026-04-28", end_date="2026-05-05")
    _upload(client, headers, _jpeg(exif=True))

    result = asyncio.run(
        TOOLS["suggest_photo_organization"].read(db, _user_id(client, headers), {})
    )
    assert result["unassigned_total"] == 1
    item = result["items"][0]
    assert item["candidates"][0]["trip_id"] == trip["id"]
    assert item["candidates"][0]["confidence"] == "medium"
    assert "storage_key" not in item["photo"]


def test_ai_update_photo_tool_only_proposes(client, db):
    headers = _headers(client, "org_ai_write")
    trip = _trip(client, headers)
    photo = _upload(client, headers, _jpeg(exif=True)).json()

    proposal = TOOLS["update_photo"].proposal(
        {"record_id": photo["id"], "data": {"trip_id": trip["id"]}}
    )
    assert proposal.action == "update_photo"
    assert proposal.record_type == "photo"
    assert proposal.data["record_id"] == photo["id"]
    assert proposal.data["trip_id"] == trip["id"]
    # A proposal never writes: the photo stays unfiled until the user saves.
    assert client.get(f"/api/v1/photos/{photo['id']}", headers=headers).json()["trip_id"] is None


def test_mcp_photo_update_waits_for_confirmation(client, db, storage):
    secret, headers = _make_write_token(client, "org_mcp")
    trip = _trip(client, headers)
    photo = _upload(client, headers, _jpeg(exif=True)).json()

    result = _mcp_call(
        client,
        secret,
        "update_record",
        {"record_type": "photo", "record_id": photo["id"], "data": {"trip_id": trip["id"]}},
    )
    assert result["status"] == "pending_confirmation", result
    assert client.get(f"/api/v1/photos/{photo['id']}", headers=headers).json()["trip_id"] is None

    body = _confirm(client, headers, result["pending_action_id"])
    assert body["result"]["record_id"] == photo["id"]
    assert (
        client.get(f"/api/v1/photos/{photo['id']}", headers=headers).json()["trip_id"] == trip["id"]
    )


def test_mcp_photo_update_foreign_photo_fails_confirmation(client):
    secret, owner_headers = _make_write_token(client, "org_mcp_owner")
    intruder_headers = _headers(client, "org_mcp_intruder")
    foreign_photo = _upload(client, intruder_headers, _jpeg(), name="theirs.jpg").json()
    trip = _trip(client, owner_headers)

    result = _mcp_call(
        client,
        secret,
        "update_record",
        {
            "record_type": "photo",
            "record_id": foreign_photo["id"],
            "data": {"trip_id": trip["id"]},
        },
    )
    response = client.post(
        f"/api/v1/pending-actions/{result['pending_action_id']}/confirm",
        json={},
        headers=owner_headers,
    )
    assert response.status_code == 400
    # The intruder's photo is untouched.
    assert (
        client.get(f"/api/v1/photos/{foreign_photo['id']}", headers=intruder_headers).json()[
            "trip_id"
        ]
        is None
    )
