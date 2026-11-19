import asyncio
import uuid
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import settings
from app.models.audit_log import AuditAction, AuditLog
from app.models.photo import Photo
from app.services import photo as photo_service
from app.services.ai_tools import TOOLS
from app.services.storage import StorageError
from tests.conftest import auth_headers, register_and_login


def _jpeg(*, exif: bool = False, size: tuple[int, int] = (64, 48)) -> bytes:
    img = Image.new("RGB", size, (120, 30, 30))
    buffer = BytesIO()
    if exif:
        meta = Image.Exif()
        meta[306] = "2026:05:01 10:30:00"
        meta[0x8769] = {36867: "2026:05:01 10:30:00", 36881: "+08:00"}
        meta[0x8825] = {
            1: "N",
            2: (1.0, 22.0, 30.5),
            3: "E",
            4: (103.0, 45.0, 12.25),
        }
        img.save(buffer, format="JPEG", exif=meta.tobytes())
    else:
        img.save(buffer, format="JPEG")
    return buffer.getvalue()


def _jpeg_without_zone() -> bytes:
    img = Image.new("RGB", (32, 32), (10, 90, 10))
    meta = Image.Exif()
    meta[0x8769] = {36867: "2026:05:01 10:30:00"}
    buffer = BytesIO()
    img.save(buffer, format="JPEG", exif=meta.tobytes())
    return buffer.getvalue()


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (40, 30), (0, 80, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(
    client,
    headers,
    data: bytes,
    *,
    name: str = "photo.jpg",
    mime: str = "image/jpeg",
    **form,
):
    return client.post(
        "/api/v1/photos",
        data=form or None,
        files={"file": (name, data, mime)},
        headers=headers,
    )


def _trip(client, headers, name: str = "SG 2026") -> dict:
    response = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _parse_utc(value: str) -> datetime:
    """Parse an API timestamp, treating a naive value as UTC.

    Postgres ``timestamptz`` comes back offset-aware; the SQLite test database
    stores the same UTC instant without a zone, so both must compare equal.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def test_upload_extracts_exif_and_stores_thumbnail(client, storage):
    token = register_and_login(client, "photo_exif")["access_token"]
    headers = auth_headers(token)
    data = _jpeg(exif=True)

    response = _upload(client, headers, data, name="../../trip.jpg")
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["filename"] == "trip.jpg"
    assert body["mime_type"] == "image/jpeg"
    assert body["size"] == len(data)
    assert "storage_key" not in body
    assert _parse_utc(body["captured_at"]) == datetime(2026, 5, 1, 2, 30, tzinfo=UTC)
    assert body["latitude"] == pytest.approx(1.375139, abs=1e-6)
    assert body["longitude"] == pytest.approx(103.753403, abs=1e-6)

    assert len(storage.objects) == 2
    main_key = f"users/{body['user_id']}/photos/{body['id']}"
    assert main_key in storage.objects
    assert storage.objects[main_key] == data
    assert storage.content_types[main_key] == "image/jpeg"

    thumbnail_key = f"{main_key}/thumb"
    assert thumbnail_key in storage.objects
    assert storage.content_types[thumbnail_key] == "image/jpeg"
    with Image.open(BytesIO(storage.objects[thumbnail_key])) as thumb:
        assert thumb.format == "JPEG"
        assert max(thumb.size) <= 480


def test_upload_without_exif_keeps_metadata_empty(client):
    token = register_and_login(client, "photo_plain")["access_token"]
    headers = auth_headers(token)

    response = _upload(client, headers, _png(), name="screenshot.png", mime="image/png")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mime_type"] == "image/png"
    assert body["captured_at"] is None
    assert body["latitude"] is None
    assert body["longitude"] is None


def test_upload_uses_browser_offset_when_exif_has_no_zone(client):
    token = register_and_login(client, "photo_offset")["access_token"]
    headers = auth_headers(token)

    response = _upload(client, headers, _jpeg_without_zone(), utc_offset_minutes=480)
    assert response.status_code == 201, response.text
    assert _parse_utc(response.json()["captured_at"]) == datetime(2026, 5, 1, 2, 30, tzinfo=UTC)


def test_actual_bytes_decide_the_type_not_the_declared_mime(client):
    """A JPEG named .txt with a text/plain content type is still a photo."""
    token = register_and_login(client, "photo_mime")["access_token"]
    headers = auth_headers(token)

    response = _upload(client, headers, _jpeg(), name="IMG_0001.txt", mime="text/plain")
    assert response.status_code == 201, response.text
    assert response.json()["mime_type"] == "image/jpeg"


@pytest.mark.parametrize(
    ("name", "mime", "payload"),
    [
        ("note.txt", "text/plain", b"just text"),
        ("evil.svg", "image/svg+xml", b"<svg onload='alert(1)'></svg>"),
        ("pass.pdf", "application/pdf", b"%PDF-1.4 test"),
        ("IMG_0001.HEIC", "image/heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"),
    ],
)
def test_upload_rejects_non_raster_images(client, name, mime, payload):
    token = register_and_login(client, f"photo_bad_{name.split('.')[-1].lower()}")["access_token"]
    response = _upload(client, auth_headers(token), payload, name=name, mime=mime)
    assert response.status_code == 415, response.text


def test_upload_size_and_pixel_limits(client, monkeypatch):
    token = register_and_login(client, "photo_limits")["access_token"]
    headers = auth_headers(token)

    response = _upload(client, headers, b"", name="empty.jpg")
    assert response.status_code == 422

    monkeypatch.setattr(settings, "max_attachment_bytes", 100)
    assert _upload(client, headers, _jpeg()).status_code == 413

    monkeypatch.setattr(settings, "max_attachment_bytes", 20 * 1024 * 1024)
    monkeypatch.setattr(photo_service, "MAX_PHOTO_PIXELS", 1000)
    assert _upload(client, headers, _jpeg()).status_code == 413


def test_photos_are_user_scoped(client, storage):
    owner = register_and_login(client, "photo_owner")["access_token"]
    intruder = register_and_login(client, "photo_intruder")["access_token"]
    owner_headers = auth_headers(owner)
    intruder_headers = auth_headers(intruder)

    photo = _upload(client, owner_headers, _jpeg()).json()

    listed = client.get("/api/v1/photos", headers=intruder_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    assert client.get(f"/api/v1/photos/{photo['id']}", headers=intruder_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/photos/{photo['id']}",
            json={"filename": "stolen.jpg"},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/photos/{photo['id']}/image", headers=intruder_headers).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/photos/{photo['id']}", headers=intruder_headers).status_code == 404
    )
    assert len(storage.objects) == 2


def test_trip_assignment_and_unlink(client):
    token = register_and_login(client, "photo_trip")["access_token"]
    headers = auth_headers(token)
    trip = _trip(client, headers)

    response = _upload(client, headers, _jpeg(), trip_id=trip["id"])
    assert response.status_code == 201, response.text
    photo = response.json()
    assert photo["trip_id"] == trip["id"]

    patched = client.patch(f"/api/v1/photos/{photo['id']}", json={"trip_id": None}, headers=headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["trip_id"] is None

    # Someone else's trip is indistinguishable from a missing trip.
    other = register_and_login(client, "photo_trip_other")["access_token"]
    other_trip = _trip(client, auth_headers(other), name="Osaka 2026")
    assert _upload(client, headers, _jpeg(), trip_id=other_trip["id"]).status_code == 404
    assert (
        client.patch(
            f"/api/v1/photos/{photo['id']}",
            json={"trip_id": other_trip["id"]},
            headers=headers,
        ).status_code
        == 404
    )


def test_patch_metadata_and_validation(client):
    token = register_and_login(client, "photo_patch")["access_token"]
    headers = auth_headers(token)
    photo = _upload(client, headers, _jpeg()).json()

    response = client.patch(
        f"/api/v1/photos/{photo['id']}",
        json={
            "filename": "../../evil.png",
            "captured_at": "2026-05-02T08:00:00Z",
            "latitude": 35.6812,
            "longitude": 139.7671,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == "evil.png"
    assert _parse_utc(body["captured_at"]) == datetime(2026, 5, 2, 8, 0, tzinfo=UTC)
    assert body["latitude"] == pytest.approx(35.6812)
    assert body["longitude"] == pytest.approx(139.7671)

    # An explicit null filename must not wipe the NOT NULL column.
    cleared = client.patch(
        f"/api/v1/photos/{photo['id']}", json={"filename": None}, headers=headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["filename"] == "evil.png"

    for payload in ({"latitude": 91}, {"latitude": -91}, {"longitude": 181}):
        assert (
            client.patch(f"/api/v1/photos/{photo['id']}", json=payload, headers=headers).status_code
            == 422
        )


def test_list_filters_search_sort_and_pagination(client):
    token = register_and_login(client, "photo_list")["access_token"]
    headers = auth_headers(token)
    trip = _trip(client, headers)

    first = _upload(client, headers, _jpeg(), name="first.jpg").json()
    second = _upload(client, headers, _jpeg(), name="second.jpg", trip_id=trip["id"]).json()
    third = _upload(client, headers, _jpeg(), name="third.jpg").json()
    client.patch(
        f"/api/v1/photos/{first['id']}",
        json={"captured_at": "2026-01-01T00:00:00Z"},
        headers=headers,
    )
    client.patch(
        f"/api/v1/photos/{second['id']}",
        json={"captured_at": "2026-03-01T00:00:00Z"},
        headers=headers,
    )

    def ids(params: dict) -> list[str]:
        response = client.get("/api/v1/photos", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["items"]]

    # Undated photos sink to the end instead of posing as newest.
    assert ids({"sort": "newest"}) == [second["id"], first["id"], third["id"]]
    assert ids({"sort": "oldest"}) == [first["id"], second["id"], third["id"]]
    assert ids({"sort": "uploaded"}) == [third["id"], second["id"], first["id"]]
    assert ids({"trip_id": trip["id"]}) == [second["id"]]
    assert ids({"search": "sec"}) == [second["id"]]

    page = client.get("/api/v1/photos", params={"page_size": 1, "page": 2}, headers=headers).json()
    assert page["total"] == 3
    assert page["page"] == 2
    assert len(page["items"]) == 1


def test_delete_removes_metadata_blobs_and_audits(client, db, storage):
    token = register_and_login(client, "photo_delete")["access_token"]
    headers = auth_headers(token)
    photo = _upload(client, headers, _jpeg()).json()
    assert len(storage.objects) == 2

    created = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.CREATE_RECORD,
            AuditLog.resource_type == "photo",
            AuditLog.resource_id == photo["id"],
        )
    )
    assert created is not None

    response = client.delete(f"/api/v1/photos/{photo['id']}", headers=headers)
    assert response.status_code == 204
    assert storage.objects == {}
    assert db.scalar(select(func.count()).select_from(Photo)) == 0
    assert client.get(f"/api/v1/photos/{photo['id']}", headers=headers).status_code == 404

    deleted = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.DELETE_RECORD,
            AuditLog.resource_type == "photo",
            AuditLog.resource_id == photo["id"],
        )
    )
    assert deleted is not None


def test_image_endpoint_serves_full_and_thumbnail_safely(client):
    token = register_and_login(client, "photo_image")["access_token"]
    headers = auth_headers(token)
    data = _jpeg()
    photo = _upload(client, headers, data).json()

    full = client.get(f"/api/v1/photos/{photo['id']}/image", headers=headers)
    assert full.status_code == 200
    assert full.content == data
    assert full.headers["content-type"].startswith("image/jpeg")
    assert full.headers["content-disposition"].startswith("inline;")
    assert full.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in full.headers["content-security-policy"]

    thumb = client.get(
        f"/api/v1/photos/{photo['id']}/image",
        params={"variant": "thumb"},
        headers=headers,
    )
    assert thumb.status_code == 200
    assert thumb.headers["content-type"].startswith("image/jpeg")
    assert thumb.content != data
    with Image.open(BytesIO(thumb.content)) as image:
        assert max(image.size) <= 480

    assert (
        client.get(
            f"/api/v1/photos/{photo['id']}/image",
            params={"variant": "huge"},
            headers=headers,
        ).status_code
        == 422
    )


def test_storage_failure_leaves_no_record(client, db, storage, monkeypatch):
    token = register_and_login(client, "photo_storage")["access_token"]
    headers = auth_headers(token)

    def boom(**_kwargs):
        raise StorageError("down")

    monkeypatch.setattr(storage, "put", boom)
    assert _upload(client, headers, _jpeg()).status_code == 502
    assert db.scalar(select(func.count()).select_from(Photo)) == 0
    assert storage.objects == {}


def test_deleting_an_account_removes_photos(client, db, storage):
    token = register_and_login(client, "photo_account")["access_token"]
    headers = auth_headers(token)
    _upload(client, headers, _jpeg())
    assert len(storage.objects) == 2

    response = client.post(
        "/api/v1/auth/me/delete", json={"password": "secret123"}, headers=headers
    )
    assert response.status_code == 204, response.text
    assert storage.objects == {}
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


def test_photo_routes_require_authentication(client):
    assert client.get("/api/v1/photos").status_code == 401


def test_trip_detail_and_map_include_photos(client):
    token = register_and_login(client, "photo_tripdetail")["access_token"]
    headers = auth_headers(token)
    trip = _trip(client, headers)
    photo = _upload(client, headers, _jpeg(exif=True), name="gps.jpg", trip_id=trip["id"]).json()

    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert [item["id"] for item in detail["photos"]] == [photo["id"]]
    assert "storage_key" not in detail["photos"][0]

    routes = client.get("/api/v1/map/routes", headers=headers).json()
    assert [item["id"] for item in routes["photos"]] == [photo["id"]]
    assert routes["photos"][0]["lat"] == pytest.approx(1.375139, abs=1e-6)
    assert routes["photos"][0]["lon"] == pytest.approx(103.753403, abs=1e-6)

    other = register_and_login(client, "photo_tripdetail_other")["access_token"]
    other_headers = auth_headers(other)
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/map/routes", headers=other_headers).json()["photos"] == []


def test_export_includes_photo_metadata_only(client):
    token = register_and_login(client, "photo_export")["access_token"]
    headers = auth_headers(token)
    trip = _trip(client, headers)
    photo = _upload(client, headers, _jpeg(exif=True), trip_id=trip["id"]).json()

    bundle = client.get("/api/v1/export?format=json", headers=headers).json()
    assert len(bundle["photos"]) == 1
    exported = bundle["photos"][0]
    assert exported["id"] == photo["id"]
    assert exported["filename"] == "photo.jpg"
    assert exported["trip_id"] == trip["id"]
    assert exported["latitude"] == pytest.approx(1.375139, abs=1e-6)
    assert "storage_key" not in exported


def test_ai_read_tools_expose_photo_metadata_only(client, db):
    token = register_and_login(client, "photo_ai")["access_token"]
    headers = auth_headers(token)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    user_id = uuid.UUID(me["id"])
    photo = _upload(client, headers, _jpeg(exif=True), name="kyoto.jpg").json()

    found = asyncio.run(TOOLS["search_photos"].read(db, user_id, {"query": "kyoto"}))
    assert found["total"] == 1
    assert found["items"][0]["filename"] == "kyoto.jpg"
    assert "storage_key" not in found["items"][0]

    single = asyncio.run(TOOLS["get_photo"].read(db, user_id, {"photo_id": photo["id"]}))
    assert single["id"] == photo["id"]
    assert single["latitude"] == pytest.approx(1.375139, abs=1e-6)

    other = register_and_login(client, "photo_ai_other")["access_token"]
    other_me = client.get("/api/v1/auth/me", headers=auth_headers(other)).json()
    missing = asyncio.run(
        TOOLS["get_photo"].read(db, uuid.UUID(other_me["id"]), {"photo_id": photo["id"]})
    )
    assert missing == {"error": "photo not found"}
