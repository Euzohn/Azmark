from pydantic import BaseModel

from app.schemas.transport import FlightRead


class RecordList(BaseModel):
    """Mixed transport types share the unified TransportRecord shape (#23)."""

    items: list[FlightRead]
    total: int
    page: int
    page_size: int
