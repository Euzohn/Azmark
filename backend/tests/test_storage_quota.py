"""Per-user storage quota: enforcement, overrides and usage accounting."""

from sqlalchemy import select

from app.models.audit_log import AuditAction, AuditLog
from tests.conftest import auth_headers, register_and_login
from tests.test_admin import _promote
from tests.test_attachments import _flight
from tests.test_attachments import _upload as _upload_attachment
from tests.test_photos import _jpeg
from tests.test_photos import _upload as _upload_photo


def _admin(client, db, name: str = "quota_admin") -> dict[str, str]:
    token = register_and_login(client, name)["access_token"]
    _promote(db, name)
    return auth_headers(token)


def _member(client, name: str) -> tuple[dict[str, str], dict]:
    token = register_and_login(client, name)["access_token"]
    headers = auth_headers(token)
    return headers, client.get("/api/v1/auth/me", headers=headers).json()


def _set_default_quota(client, admin, value: int) -> dict:
    response = client.patch(
        "/api/v1/admin/settings",
        json={"default_storage_quota_bytes": value},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_user_quota(client, admin, user_id: str, value: int | None) -> dict:
    response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"storage_quota_bytes": value},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _usage(client, headers) -> dict:
    response = client.get("/api/v1/settings/storage", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_storage_usage_requires_auth(client):
    assert client.get("/api/v1/settings/storage").status_code == 401


def test_unlimited_by_default_and_usage_counts_attachments_and_photos(client):
    headers, _ = _member(client, "quota_usage")
    flight = _flight(client, headers)
    attachment = _upload_attachment(client, headers, "flight", flight["id"]).json()
    photo = _upload_photo(client, headers, _jpeg()).json()

    usage = _usage(client, headers)
    assert usage["unlimited"] is True
    assert usage["quota_bytes"] == 0
    assert usage["used_bytes"] == attachment["size"] + photo["size"]


def test_default_quota_blocks_both_upload_paths(client, db):
    admin = _admin(client, db)
    headers, _ = _member(client, "quota_blocked")
    flight = _flight(client, headers)
    attachment = _upload_attachment(client, headers, "flight", flight["id"]).json()
    _set_default_quota(client, admin, attachment["size"])

    blocked_attachment = _upload_attachment(
        client, headers, "flight", flight["id"], name="tiny.pdf", data=b"x"
    )
    assert blocked_attachment.status_code == 507
    assert _upload_photo(client, headers, _jpeg()).status_code == 507

    # Nothing was stored, so usage is unchanged.
    assert _usage(client, headers)["used_bytes"] == attachment["size"]


def test_quota_boundary_is_inclusive(client, db):
    admin = _admin(client, db)
    headers, _ = _member(client, "quota_boundary")
    flight = _flight(client, headers)
    first = _upload_attachment(client, headers, "flight", flight["id"], name="a.bin", data=b"12345")
    assert first.status_code == 201, first.text
    _set_default_quota(client, admin, 10)

    exactly = _upload_attachment(
        client, headers, "flight", flight["id"], name="b.bin", data=b"abcde"
    )
    assert exactly.status_code == 201, exactly.text
    assert _usage(client, headers)["used_bytes"] == 10

    over = _upload_attachment(client, headers, "flight", flight["id"], name="c.bin", data=b"f")
    assert over.status_code == 507


def test_per_user_override_wins_and_null_resets(client, db):
    admin = _admin(client, db)
    headers, me = _member(client, "quota_override")
    _set_default_quota(client, admin, 0)  # instance default: unlimited

    tightened = _set_user_quota(client, admin, me["id"], 1)
    assert tightened["storage_quota_bytes"] == 1
    assert tightened["effective_quota_bytes"] == 1
    assert _usage(client, headers)["unlimited"] is False

    flight = _flight(client, headers)
    assert _upload_attachment(client, headers, "flight", flight["id"], data=b"x").status_code == 201
    assert _upload_attachment(client, headers, "flight", flight["id"], data=b"y").status_code == 507

    # Explicit null resets the override: follow the instance default again.
    reset = _set_user_quota(client, admin, me["id"], None)
    assert reset["storage_quota_bytes"] is None
    assert reset["effective_quota_bytes"] == 0
    assert _usage(client, headers)["unlimited"] is True


def test_admin_is_exempt_from_enforcement(client, db):
    admin = _admin(client, db)
    admin_me = client.get("/api/v1/auth/me", headers=admin).json()
    _set_user_quota(client, admin, admin_me["id"], 1)

    flight = _flight(client, admin)
    response = _upload_attachment(client, admin, "flight", flight["id"], data=b"payload")
    assert response.status_code == 201, response.text
    # The user-facing card never shows admins a blocking limit either.
    assert _usage(client, admin)["unlimited"] is True


def test_negative_quota_is_rejected(client, db):
    admin = _admin(client, db)
    _, me = _member(client, "quota_negative")

    response = client.patch(
        "/api/v1/admin/settings",
        json={"default_storage_quota_bytes": -1},
        headers=admin,
    )
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/admin/users/{me['id']}",
        json={"storage_quota_bytes": -1},
        headers=admin,
    )
    assert response.status_code == 422


def test_quota_change_is_audited_and_listed(client, db):
    admin = _admin(client, db)
    _, me = _member(client, "quota_audit")
    _set_user_quota(client, admin, me["id"], 1024)

    logs = db.scalars(
        select(AuditLog).where(
            AuditLog.action == AuditAction.ADMIN_UPDATE_USER,
            AuditLog.resource_id == me["id"],
        )
    ).all()
    assert any("storage_quota_bytes" in (log.meta or {}).get("fields", []) for log in logs)

    listed = client.get("/api/v1/admin/users", headers=admin).json()
    item = next(entry for entry in listed["items"] if entry["id"] == me["id"])
    assert item["storage_quota_bytes"] == 1024
    assert item["effective_quota_bytes"] == 1024


def test_usage_is_user_scoped_and_deleting_frees_quota(client, db):
    admin = _admin(client, db)
    headers, _ = _member(client, "quota_scope")
    other_headers, _ = _member(client, "quota_scope_other")
    flight = _flight(client, headers)
    attachment = _upload_attachment(
        client, headers, "flight", flight["id"], name="a.bin", data=b"123456"
    ).json()

    assert _usage(client, headers)["used_bytes"] == 6
    assert _usage(client, other_headers)["used_bytes"] == 0

    _set_default_quota(client, admin, 6)
    assert _upload_attachment(client, headers, "flight", flight["id"], data=b"x").status_code == 507

    deleted = client.delete(f"/api/v1/attachments/{attachment['id']}", headers=headers)
    assert deleted.status_code == 204
    assert _usage(client, headers)["used_bytes"] == 0
    assert _upload_attachment(client, headers, "flight", flight["id"], data=b"x").status_code == 201
