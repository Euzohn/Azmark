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
    assert bundle["version"] == 2
    assert bundle["bundle_id"]
    assert bundle["settings"]["timezone"] == "UTC"
    assert len(bundle["records"]) == 1
    record = bundle["records"][0]
    assert record["service_number"] == "CA985"
    assert record["id"]
    assert record["trip_id"] == trip["id"]
    assert "trip_name" not in record
    assert "booking_reference" not in record


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


def test_import_normalizes_status_aliases(client):
    """A free-form status column is normalized, never a row error (B-tier)."""
    token = register_and_login(client, "import_status")["access_token"]
    headers = auth_headers(token)
    csv_text = (
        "type,from,to,date,status,flight_number\n"
        "flight,PEK,SFO,2026-08-01T08:00:00Z,delayed,CA985\n"
        "flight,SFO,PEK,2026-08-10T08:00:00Z,landed,CA986\n"
        "flight,SFO,LAX,2026-09-01T08:00:00Z,bogus,CA987\n"
    )
    response = _commit(client, headers, csv_text)
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 3
    assert response.json()["failed"] == 0

    flights = client.get("/api/v1/flights", headers=headers).json()["items"]
    by_number = {f["service_number"]: f["status"] for f in flights}
    # delayed → scheduled (alias), landed → completed (alias), bogus → default
    assert by_number == {"CA985": "scheduled", "CA986": "completed", "CA987": "scheduled"}


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


def test_export_json_includes_expenses_and_notes(client):
    token = register_and_login(client, "export_expense_note")["access_token"]
    headers = auth_headers(token)
    trip = client.post("/api/v1/trips", json={"name": "Osaka 2026"}, headers=headers).json()
    expense = client.post(
        "/api/v1/expenses",
        json={
            "category": "food",
            "amount": "18.00",
            "currency": "JPY",
            "occurred_at": "2026-04-02T12:00:00Z",
            "trip_id": trip["id"],
        },
        headers=headers,
    )
    assert expense.status_code == 201, expense.text
    note = client.post(
        "/api/v1/notes",
        json={"title": "Osaka plan", "content": "Dotonbori", "trip_id": trip["id"]},
        headers=headers,
    )
    assert note.status_code == 201, note.text

    bundle = client.get("/api/v1/export?format=json", headers=headers).json()
    assert len(bundle["expenses"]) == 1
    assert bundle["expenses"][0]["amount"] == "18.00"
    assert bundle["expenses"][0]["currency"] == "JPY"
    assert bundle["expenses"][0]["trip_id"] == trip["id"]
    assert "trip_name" not in bundle["expenses"][0]
    assert len(bundle["notes"]) == 1
    assert bundle["notes"][0]["title"] == "Osaka plan"
    assert bundle["notes"][0]["trip_id"] == trip["id"]
    assert "trip_name" not in bundle["notes"][0]


def test_export_json_includes_places_and_activities(client):
    token = register_and_login(client, "export_place_activity")["access_token"]
    headers = auth_headers(token)
    trip = client.post("/api/v1/trips", json={"name": "Osaka 2026"}, headers=headers).json()
    place = client.post(
        "/api/v1/places",
        json={"name": "Dotonbori", "type": "attraction", "city": "Osaka", "lat": 34.6687},
        headers=headers,
    )
    assert place.status_code == 201, place.text
    activity = client.post(
        "/api/v1/activities",
        json={
            "name": "Street food crawl",
            "type": "dining",
            "place_id": place.json()["id"],
            "trip_id": trip["id"],
            "start_at": "2026-04-02T18:00:00Z",
            "price": "4200",
            "currency": "jpy",
        },
        headers=headers,
    )
    assert activity.status_code == 201, activity.text

    bundle = client.get("/api/v1/export?format=json", headers=headers).json()
    assert len(bundle["places"]) == 1
    assert bundle["places"][0]["name"] == "Dotonbori"
    assert bundle["places"][0]["lat"] == 34.6687
    assert len(bundle["activities"]) == 1
    exported = bundle["activities"][0]
    assert exported["name"] == "Street food crawl"
    assert exported["currency"] == "JPY"
    assert exported["place_id"] == place.json()["id"]
    assert exported["trip_id"] == trip["id"]
    assert "trip_name" not in exported


def _trip_sequence(detail: dict) -> list[str]:
    """Orderable labels for a trip timeline, independent of target UUIDs."""
    labels: list[str] = []
    for item in detail["items"]:
        if item["item_type"] == "transport":
            labels.append(f"transport:{item['record']['service_number']}")
        elif item["item_type"] == "hotel":
            labels.append(f"hotel:{item['hotel']['hotel']}")
        else:
            labels.append(f"activity:{item['activity']['name']}")
    return labels


def test_v2_roundtrip_restores_relations_order_and_spend(client):
    token_a = register_and_login(client, "v2_a")["access_token"]
    token_b = register_and_login(client, "v2_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    trip = client.post(
        "/api/v1/trips",
        json={"name": "Europe 2026", "timeline_order_mode": "manual"},
        headers=headers_a,
    ).json()
    place = client.post(
        "/api/v1/places",
        json={"name": "Dotonbori", "type": "attraction", "city": "Osaka"},
        headers=headers_a,
    ).json()
    client.post("/api/v1/flights", json={**_flight(), "trip_id": trip["id"]}, headers=headers_a)
    hotel = client.post(
        "/api/v1/hotels",
        json={
            "hotel": "Hotel Osaka",
            "check_in": "2026-08-02",
            "check_out": "2026-08-05",
            "trip_id": trip["id"],
            "price": "300.00",
            "currency": "EUR",
        },
        headers=headers_a,
    ).json()
    client.post(
        "/api/v1/activities",
        json={
            "name": "Street food crawl",
            "type": "dining",
            "place_id": place["id"],
            "trip_id": trip["id"],
            "start_at": "2026-08-03T18:00:00Z",
        },
        headers=headers_a,
    )
    detail_a = client.get(f"/api/v1/trips/{trip['id']}", headers=headers_a).json()
    reversed_ids = [item["id"] for item in reversed(detail_a["items"])]
    reordered = client.put(
        f"/api/v1/trips/{trip['id']}/items/order",
        json={"item_ids": reversed_ids},
        headers=headers_a,
    )
    assert reordered.status_code == 204, reordered.text

    expense = client.post(
        "/api/v1/expenses",
        json={
            "category": "accommodation",
            "amount": "300.00",
            "currency": "EUR",
            "source_type": "hotel",
            "source_id": hotel["id"],
        },
        headers=headers_a,
    )
    assert expense.status_code == 201, expense.text
    note = client.post(
        "/api/v1/notes",
        json={"title": "Osaka plan", "content": "Dotonbori at night", "trip_id": trip["id"]},
        headers=headers_a,
    )
    assert note.status_code == 201, note.text

    detail_a = client.get(f"/api/v1/trips/{trip['id']}", headers=headers_a).json()
    expected_sequence = _trip_sequence(detail_a)
    exported = client.get("/api/v1/export?format=json", headers=headers_a).text

    response = _commit(client, headers_b, exported, filename="backup.json", fmt="json")
    assert response.status_code == 200, response.text
    assert response.json()["trips_created"] == 1

    trips_b = client.get("/api/v1/trips", headers=headers_b).json()
    assert trips_b["total"] == 1
    trip_b = trips_b["items"][0]
    assert trip_b["timeline_order_mode"] == "manual"

    detail_b = client.get(f"/api/v1/trips/{trip_b['id']}", headers=headers_b).json()
    assert _trip_sequence(detail_b) == expected_sequence
    assert len(detail_b["expenses"]) == 1
    assert detail_b["expenses"][0]["source_type"] == "hotel"
    assert detail_b["notes"][0]["title"] == "Osaka plan"

    hotels_b = client.get("/api/v1/hotels", headers=headers_b).json()["items"]
    assert len(hotels_b) == 1
    assert detail_b["expenses"][0]["source_id"] == hotels_b[0]["id"]
    assert detail_b["expenses"][0]["trip_id"] == trip_b["id"]

    activities_b = client.get("/api/v1/activities", headers=headers_b).json()["items"]
    places_b = client.get("/api/v1/places", headers=headers_b).json()["items"]
    assert activities_b[0]["place_id"] == places_b[0]["id"]

    # Same bundle again: every business entity maps to the original target.
    again = _commit(client, headers_b, exported, filename="backup.json", fmt="json")
    assert again.status_code == 200, again.text
    assert again.json()["imported"] == 0
    assert again.json()["trips_created"] == 0
    assert client.get("/api/v1/trips", headers=headers_b).json()["total"] == 1
    assert client.get("/api/v1/expenses", headers=headers_b).json()["total"] == 1


def test_v2_import_rejects_changed_content_for_same_bundle(client):
    token = register_and_login(client, "v2_conflict")["access_token"]
    headers = auth_headers(token)
    trip = client.post("/api/v1/trips", json={"name": "Original"}, headers=headers).json()
    assert trip["id"]

    bundle = client.get("/api/v1/export?format=json", headers=headers).json()
    first = _commit(client, headers, json.dumps(bundle), filename="b.json", fmt="json")
    assert first.status_code == 200, first.text

    bundle["trips"][0]["name"] = "Changed"
    response = _commit(client, headers, json.dumps(bundle), filename="b.json", fmt="json")
    assert response.status_code == 422
    assert "changed content" in response.json()["detail"]
    assert client.get("/api/v1/trips", headers=headers).json()["items"][0]["name"] == "Original"


def test_v2_import_rejects_missing_source_and_rolls_back(client):
    token_a = register_and_login(client, "v2_missing_a")["access_token"]
    token_b = register_and_login(client, "v2_missing_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    trip = client.post("/api/v1/trips", json={"name": "Broken"}, headers=headers_a).json()
    hotel = client.post(
        "/api/v1/hotels",
        json={"hotel": "Hotel", "check_in": "2026-08-02", "trip_id": trip["id"]},
        headers=headers_a,
    ).json()
    expense = client.post(
        "/api/v1/expenses",
        json={
            "category": "accommodation",
            "amount": "10.00",
            "currency": "EUR",
            "source_type": "hotel",
            "source_id": hotel["id"],
        },
        headers=headers_a,
    )
    assert expense.status_code == 201, expense.text

    bundle = client.get("/api/v1/export?format=json", headers=headers_a).json()
    bundle["hotels"] = []
    response = _commit(client, headers_b, json.dumps(bundle), filename="bad.json", fmt="json")
    assert response.status_code == 422
    # The whole bundle is atomic: nothing was created before the failure.
    assert client.get("/api/v1/trips", headers=headers_b).json()["total"] == 0
    assert client.get("/api/v1/expenses", headers=headers_b).json()["total"] == 0


def test_v2_preview_validates_references_without_writing(client):
    token_a = register_and_login(client, "v2_preview_a")["access_token"]
    token_b = register_and_login(client, "v2_preview_b")["access_token"]
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    trip = client.post("/api/v1/trips", json={"name": "Preview"}, headers=headers_a).json()
    client.post(
        "/api/v1/places",
        json={"name": "Somewhere", "type": "city"},
        headers=headers_a,
    )
    client.post("/api/v1/flights", json={**_flight(), "trip_id": trip["id"]}, headers=headers_a)
    export = client.get("/api/v1/export?format=json", headers=headers_a).text

    preview = client.post(
        "/api/v1/import/preview",
        files={"file": ("backup.json", export.encode("utf-8"), "application/json")},
        data={"format": "json"},
        headers=headers_b,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["error_count"] == 0
    assert body["valid"] > 0
    assert body["columns"] == []
    # Preview never writes.
    assert client.get("/api/v1/trips", headers=headers_b).json()["total"] == 0

    broken = json.loads(export)
    broken["trips"] = []
    bad = client.post(
        "/api/v1/import/preview",
        files={"file": ("bad.json", json.dumps(broken).encode("utf-8"), "application/json")},
        data={"format": "json"},
        headers=headers_b,
    )
    assert bad.status_code == 200, bad.text
    assert bad.json()["error_count"] >= 1


def test_v1_json_still_imports_records(client):
    token = register_and_login(client, "v1_json")["access_token"]
    headers = auth_headers(token)
    legacy = {
        "version": 1,
        "trips": [{"name": "Legacy 2026"}],
        "records": [
            {
                "type": "flight",
                "origin": "PEK",
                "destination": "SFO",
                "departure_time": "2026-08-01T08:00:00Z",
                "service_number": "CA985",
                "trip_name": "Legacy 2026",
            }
        ],
    }
    response = _commit(client, headers, json.dumps(legacy), filename="v1.json", fmt="json")
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 1
    flights = client.get("/api/v1/flights", headers=headers).json()
    assert flights["total"] == 1


def test_v1_json_preview_warns_about_unsupported_arrays(client):
    token = register_and_login(client, "v1_warn")["access_token"]
    headers = auth_headers(token)
    legacy = {
        "version": 1,
        "trips": [{"name": "Legacy 2026"}],
        "records": [
            {
                "type": "flight",
                "origin": "PEK",
                "destination": "SFO",
                "departure_time": "2026-08-01T08:00:00Z",
                "service_number": "CA985",
                "trip_name": "Legacy 2026",
            }
        ],
        "expenses": [{"amount": "10.00", "currency": "EUR"}],
        "notes": [{"title": "Ignored"}],
    }
    preview = _upload(
        client,
        headers,
        json.dumps(legacy),
        filename="v1.json",
        fmt="json",
    )
    assert preview.status_code == 200, preview.text
    warnings = preview.json()["warnings"]
    assert any("expenses" in warning for warning in warnings)
    assert any("notes" in warning for warning in warnings)
    assert all("records" not in warning for warning in warnings)
