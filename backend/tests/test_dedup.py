import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date
from sqlalchemy.dialects import postgresql

from app.repositories.transport import TransportRepository
from app.services.dedup import record_signature, record_signature_from_model


class _FakeSession:
    """Captures the statement instead of executing it."""

    def __init__(self) -> None:
        self.stmt = None

    def scalar(self, stmt):
        self.stmt = stmt
        return None


def test_signature_is_normalized():
    sig = record_signature(
        record_type="flight",
        payload={
            "departure_time": datetime(2026, 9, 26, 8, 0, tzinfo=UTC),
            "carrier": "  CX ",
            "service_number": " cx659 ",
            "origin": "HKG ",
            "destination": " SIN",
        },
    )
    assert sig == "flight|2026-09-26|cx|CX659|hkg|sin"


def test_signature_uses_utc_date():
    sig = record_signature(
        record_type="train",
        payload={
            "departure_time": datetime(2026, 9, 26, 23, 30, tzinfo=UTC),
            "origin": "北京南",
            "destination": "上海虹桥",
            "service_number": "G1",
        },
    )
    assert sig.split("|")[1] == "2026-09-26"


def test_signature_from_model_matches_payload_signature():
    class _Record:
        type = "flight"
        departure_time = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)
        carrier = "CX"
        service_number = "CX659"
        origin = "HKG"
        destination = "SIN"

    payload_sig = record_signature(
        record_type="flight",
        payload={
            "departure_time": datetime(2026, 9, 26, 8, 0, tzinfo=UTC),
            "carrier": "CX",
            "service_number": "CX659",
            "origin": "HKG",
            "destination": "SIN",
        },
    )
    assert record_signature_from_model(_Record()) == payload_sig


def test_signature_query_binds_date_for_postgres():
    """`func.date()` is NullType; a plain string makes PG reject `date = varchar`."""
    session = _FakeSession()
    repo = TransportRepository(session)  # type: ignore[arg-type]

    repo.find_by_signature(
        user_id=uuid.uuid4(),
        signature="flight|2026-09-26|cx|CX659|hkg|sin",
    )

    assert session.stmt is not None
    compiled = session.stmt.compile(dialect=postgresql.dialect())
    assert Date in {type(bind.type) for bind in compiled.binds.values()}
    assert date(2026, 9, 26) in compiled.params.values()
