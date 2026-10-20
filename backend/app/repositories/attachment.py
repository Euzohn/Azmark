import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment


class AttachmentRepository:
    """Attachment metadata queries, always scoped by user_id (spec #57)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, attachment: Attachment) -> Attachment:
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def get(self, *, user_id: uuid.UUID, attachment_id: uuid.UUID) -> Attachment | None:
        return self.db.scalar(
            select(Attachment).where(
                Attachment.id == attachment_id,
                Attachment.user_id == user_id,
            )
        )

    def list_for_resource(
        self,
        *,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> list[Attachment]:
        stmt = (
            select(Attachment)
            .where(
                Attachment.user_id == user_id,
                Attachment.resource_type == resource_type,
                Attachment.resource_id == resource_id,
            )
            .order_by(Attachment.created_at.desc(), Attachment.id)
        )
        return list(self.db.scalars(stmt))

    def list_for_user(self, *, user_id: uuid.UUID) -> list[Attachment]:
        stmt = select(Attachment).where(Attachment.user_id == user_id)
        return list(self.db.scalars(stmt))

    def delete(self, attachment: Attachment) -> None:
        self.db.delete(attachment)
        self.db.commit()

    def delete_many(self, attachments: list[Attachment]) -> None:
        for attachment in attachments:
            self.db.delete(attachment)
        self.db.commit()
