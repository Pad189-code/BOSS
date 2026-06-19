from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailRequestSummary(BaseModel):
    id: UUID
    external_id: str | None
    provider: str
    from_address: str
    subject: str | None
    body_preview: str
    received_at: datetime
    status: str


class EmailSyncResult(BaseModel):
    fetched: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    message_ids: list[str] = Field(default_factory=list)


class EmailProcessResult(BaseModel):
    email_request_id: UUID
    quote_id: UUID
    numero_offre: str
