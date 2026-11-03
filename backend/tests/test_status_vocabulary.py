"""The status vocabulary is closed on every write path (B-tier tightening).

Legacy DB rows stay readable (Read schemas remain permissive ``str``), but
create / update / list filter / import all enforce or normalize the canonical
values, so no new junk status can enter the system from any entry point.
"""

from app.schemas.status import (
    canonical_record_status,
    canonical_trip_status,
    normalize_record_status,
    normalize_trip_status,
)
from tests.conftest import auth_headers, register_and_login

FLIGHT = {
    "origin": "HKG",
    "destination": "SIN",
    "departure_time": "2026-09-26T01:45:00Z",
    "service_number": "CX659",
}

HOTEL = {"hotel": "Marina Bay", "check_in": "2026-09-26"}


# -- alias / normalization unit tests ---------------------------------------


def test_canonical_record_status_maps_aliases_and_is_case_insensitive():
    assert canonical_record_status("landed") == "completed"
    assert canonical_record_status("落地") == "completed"
    assert canonical_record_status("CANCELLED") == "cancelled"
    assert canonical_record_status("  scheduled ") == "scheduled"
    assert canonical_record_status(None) is None
    assert canonical_record_status("") is None
    assert canonical_record_status("totally-bogus") is None


def test_normalize_record_status_falls_back_to_default():
    assert normalize_record_status("delayed") == "scheduled"
    assert normalize_record_status("bogus") == "scheduled"
    assert normalize_record_status(None) == "scheduled"


def test_canonical_trip_status_maps_aliases():
    assert canonical_trip_status("done") == "completed"
    assert canonical_trip_status("active") == "ongoing"
    assert canonical_trip_status("upcoming") == "planned"
    assert canonical_trip_status("canceled") == "cancelled"
    assert normalize_trip_status("weird") == "planned"


# -- REST create/update rejects unknown statuses ----------------------------


def test_flight_create_rejects_unknown_status(client):
    token = register_and_login(client, "status_flight")["access_token"]
    headers = auth_headers(token)

    bad = client.post("/api/v1/flights", json={**FLIGHT, "status": "delayed"}, headers=headers)
    assert bad.status_code == 422

    good = client.post("/api/v1/flights", json={**FLIGHT, "status": "cancelled"}, headers=headers)
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "cancelled"

    # update path is closed too
    flight_id = good.json()["id"]
    patched = client.patch(
        f"/api/v1/flights/{flight_id}", json={"status": "landed"}, headers=headers
    )
    assert patched.status_code == 422


def test_hotel_create_rejects_unknown_status(client):
    token = register_and_login(client, "status_hotel")["access_token"]
    headers = auth_headers(token)

    bad = client.post("/api/v1/hotels", json={**HOTEL, "status": "delayed"}, headers=headers)
    assert bad.status_code == 422

    good = client.post("/api/v1/hotels", json={**HOTEL, "status": "completed"}, headers=headers)
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "completed"


def test_trip_create_rejects_unknown_status(client):
    token = register_and_login(client, "status_trip")["access_token"]
    headers = auth_headers(token)

    bad = client.post("/api/v1/trips", json={"name": "Tokyo", "status": "boarded"}, headers=headers)
    assert bad.status_code == 422

    good = client.post(
        "/api/v1/trips", json={"name": "Tokyo", "status": "ongoing"}, headers=headers
    )
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "ongoing"


# -- list filters reject unknown statuses -----------------------------------


def test_records_and_hotels_filters_reject_unknown_status(client):
    token = register_and_login(client, "status_filter")["access_token"]
    headers = auth_headers(token)

    assert client.get("/api/v1/records?status=bogus", headers=headers).status_code == 422
    assert client.get("/api/v1/hotels?status=bogus", headers=headers).status_code == 422
    # valid values are accepted
    assert client.get("/api/v1/records?status=scheduled", headers=headers).status_code == 200
    assert client.get("/api/v1/hotels?status=completed", headers=headers).status_code == 200
