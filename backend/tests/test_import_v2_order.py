"""Route-level v2 import regression: parent trips must precede member rows.

The importer overwrites prepared primary keys; on FK-enforcing databases
(Postgres) the unit of work may insert child rows before their parent trip
unless trips are flushed first. SQLite hides this unless foreign_keys=ON
(conftest enables it), so this test pins the ordering through the real route.
"""

import json
import uuid

from sqlalchemy import select

from app.models.transport_record import TransportRecord
from app.models.trip import Trip
from app.models.trip_item import TripItem
from tests.conftest import auth_headers, register_and_login


def _bundle() -> dict:
    trip_id, flight_id, train_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

    def record(rid: str, type_: str, no: str) -> dict:
        return {
            "id": rid,
            "trip_id": trip_id,
            "type": type_,
            "status": "completed",
            "departure_time": "2026-05-01T09:00:00+08:00",
            "arrival_time": "2026-05-01T13:28:00+08:00",
            "departure_timezone": "Asia/Shanghai",
            "arrival_timezone": "Asia/Shanghai",
            "origin": "北京南" if type_ == "train" else "PEK",
            "destination": "上海虹桥" if type_ == "train" else "SHA",
            "carrier": "中国铁路" if type_ == "train" else "中国国际航空",
            "service_number": no,
            "price": 553,
            "currency": "CNY",
        }

    return {
        "version": 2,
        "bundle_id": str(uuid.uuid4()),
        "trips": [
            {
                "id": trip_id,
                "name": " ordering probe ",
                "start_date": "2026-05-01",
                "end_date": "2026-05-04",
                "status": "completed",
                "timeline_order_mode": "chronological",
            }
        ],
        "records": [record(flight_id, "flight", "CA1501"), record(train_id, "train", "G103")],
        "trip_items": [
            {
                "id": str(uuid.uuid4()),
                "trip_id": trip_id,
                "item_type": "transport",
                "item_id": flight_id,
                "sort_order": 0,
            },
            {
                "id": str(uuid.uuid4()),
                "trip_id": trip_id,
                "item_type": "transport",
                "item_id": train_id,
                "sort_order": 1,
            },
        ],
    }


def test_v2_import_route_inserts_trips_before_members(client, db):
    headers = auth_headers(register_and_login(client, "importorder")["access_token"])
    content = json.dumps(_bundle(), ensure_ascii=False)
    files = {"file": ("bundle.json", content.encode("utf-8"), "application/json")}
    preview = client.post("/api/v1/import/preview", files=files, headers=headers)
    assert preview.status_code == 200, preview.text
    files = {"file": ("bundle.json", content.encode("utf-8"), "application/json")}
    response = client.post("/api/v1/import", files=files, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 2 and body["trips_created"] == 1, body

    trip = db.scalars(select(Trip).where(Trip.name == " ordering probe ")).one()
    records = db.scalars(select(TransportRecord)).all()
    assert len(records) == 2
    assert all(r.trip_id == trip.id for r in records)
    assert len(db.scalars(select(TripItem)).all()) == 2
