import csv
import io
import json

from tests.conftest import auth_headers, register_and_login


def _flight(**overrides):
    data = {
        "origin": "PEK",
        "destination": "SFO",
        "departure_time": "2026-08-01T08:00:00Z",
        "arrival_time": "2026-08-01T11:30:00Z",
        "carrier": "Air China",
        "service_number": "CA985",
        "booking_reference": "ABC123",
    }
    data.update(overrides)
    return data


def _upload(client, headers, content, filename="records.csv", fmt="csv", mapping=None):
    data = {"format": fmt}
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    return client.post(
        "/api/v1/import/preview",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
        data=data,
        headers=headers,
    )


def _commit(client, headers, content, filename="records.csv", fmt="csv", mapping=None):
    data = {"format": fmt}
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    return client.post(
        "/api/v1/import",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
        data=data,
        headers=headers,
    )


def test_export_json_bundle(client):
    token = register_and_login(client, "export_json")["access_token"]
    headers = auth_headers(token)
    trip = client.post(
        "/api/v1/trips",
        json={"name": "Summer 2026", "start_date": "2026-08-01"},
        headers=headers,
    ).json()
    created = client.post(
        "/api/v1/flights", json={**_flight(), "trip_id": trip["id"]}, headers=headers
    )
    assert created.status_code == 201, created.text

    response = client.get("/api/v1/export?format=json", headers=headers)
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    bundle = response.json()
    assert bundle["version"] == 1
    assert bundle["settings"]["timezone"] == "UTC"
    assert len(bundle["records"]) == 1
    assert bundle["records"][0]["service_number"] == "CA985"
    assert bundle["records"][0]["trip_name"] == "Summer 2026"
    assert "booking_reference" not in bundle["records"][0]


def test_export_csv_and_sensitive_opt_in(client):
    token = register_and_login(client, "export_csv")["access_token"]
    headers = auth_headers(token)
    assert client.post("/api/v1/flights", json=_flight(), headers=headers).status_code == 201

    response = client.get("/api/v1/export?format=csv", headers=headers)
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["origin"] == "PEK"
    assert "booking_reference" not in rows[0]

    response = client.get("/api/v1/export?format=csv&include_sensitive=true", headers=headers)
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["booking_reference"] == "ABC123"


def test_export_is_user_scoped(client):
    token_a = register_and_login(client, "export_a")["access_token"]
    token_b = register_and_login(client, "export_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)
    assert client.post("/api/v1/flights", json=_flight(), headers=headers_a).status_code == 201

    bundle_b = client.get("/api/v1/export?format=json", headers=headers_b).json()
    assert bundle_b["records"] == []
    assert bundle_b["trips"] == []


def test_import_preview_reports_valid_duplicates_and_errors(client):
    token = register_and_login(client, "preview")["access_token"]
    headers = auth_headers(token)
    assert client.post("/api/v1/flights", json=_flight(), headers=headers).status_code == 201

    csv_text = (
        "from,to,date,flight_number,airline\n"
        "PEK,SFO,2026-08-01T08:00:00Z,CA985,Air China\n"  # duplicate
        "SHA,NRT,2026-09-01T08:00:00Z,MU523,China Eastern\n"  # valid
        "SHA,,2026-09-02T08:00:00Z,MU524,China Eastern\n"  # missing destination
    )
    response = _upload(client, headers, csv_text)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["valid"] == 1
    assert body["duplicate_count"] == 1
    assert body["error_count"] == 1
    assert body["field_mapping"]["from"] == "origin"
    assert body["field_mapping"]["flight_number"] == "service_number"
    assert body["rows"][0]["origin"] == "SHA"
    assert body["rows"][0]["type"] == "flight"


def test_import_commit_creates_records_and_trip(client):
    token = register_and_login(client, "commit")["access_token"]
    headers = auth_headers(token)
    csv_text = (
        "type,from,to,date,flight_number,airline,trip\n"
        "flight,PEK,SFO,2026-08-01T08:00:00Z,CA985,Air China,Summer 2026\n"
        "train,PEK,SHA,2026-08-05T09:00:00Z,G1,CRH,Summer 2026\n"
    )
    response = _commit(client, headers, csv_text)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "imported": 2,
        "skipped_duplicates": 0,
        "failed": 0,
        "trips_created": 1,
        "errors": [],
    }

    flights = client.get("/api/v1/flights", headers=headers).json()
    trains = client.get("/api/v1/trains", headers=headers).json()
    trips = client.get("/api/v1/trips", headers=headers).json()
    assert flights["total"] == 1
    assert trains["total"] == 1
    assert trips["total"] == 1
    assert flights["items"][0]["trip_id"] == trips["items"][0]["id"]

    # re-importing the same file skips everything
    again = _commit(client, headers, csv_text).json()
    assert again["imported"] == 0
    assert again["skipped_duplicates"] == 2


def test_import_json_roundtrip_between_users(client):
    token_a = register_and_login(client, "roundtrip_a")["access_token"]
    token_b = register_and_login(client, "roundtrip_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    trip = client.post("/api/v1/trips", json={"name": "Europe 2026"}, headers=headers_a).json()
    client.post("/api/v1/flights", json={**_flight(), "trip_id": trip["id"]}, headers=headers_a)
    client.post(
        "/api/v1/trains",
        json={
            "origin": "SFO",
            "destination": "LAX",
            "departure_time": "2026-08-10T09:00:00Z",
            "service_number": "Amtrak 11",
            "trip_id": trip["id"],
        },
        headers=headers_a,
    )

    exported = client.get("/api/v1/export?format=json", headers=headers_a).text
    response = _commit(client, headers_b, exported, filename="backup.json", fmt="json")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 2
    assert body["trips_created"] == 1

    flights_b = client.get("/api/v1/flights", headers=headers_b).json()
    trains_b = client.get("/api/v1/trains", headers=headers_b).json()
    trips_b = client.get("/api/v1/trips", headers=headers_b).json()
    assert flights_b["total"] == 1
    assert trains_b["total"] == 1
    assert trips_b["total"] == 1
    assert flights_b["items"][0]["trip_id"] == trips_b["items"][0]["id"]


def test_import_mapping_override_and_template(client):
    token = register_and_login(client, "mapping")["access_token"]
    headers = auth_headers(token)
    csv_text = "place_a,place_b,when\nPEK,SFO,2026-08-01T08:00:00Z\n"
    response = _upload(
        client,
        headers,
        csv_text,
        mapping={"place_a": "origin", "place_b": "destination", "when": "departure_time"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] == 1
    assert body["rows"][0]["origin"] == "PEK"

    template = client.get("/api/v1/import/template?format=csv")
    assert template.status_code == 200
    assert "service_number" in template.text.splitlines()[0]


def test_import_counts_only_new_trips(client):
    token = register_and_login(client, "trip_count")["access_token"]
    headers = auth_headers(token)
    client.post("/api/v1/trips", json={"name": "Japan 2026"}, headers=headers)
    csv_text = (
        "type,origin,destination,service_number,departure_time,trip\n"
        "flight,PEK,NRT,CA925,2026-04-01T08:00:00Z,Japan 2026\n"
    )
    response = _commit(client, headers, csv_text)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 1
    assert body["trips_created"] == 0
