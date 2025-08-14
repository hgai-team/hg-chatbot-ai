from pydantic import BaseModel
from typing import Any

class FileResponse(BaseModel):
    status: int


import uuid

from enum import Enum
from datetime import datetime

from typing import Optional

from sqlmodel import Field, SQLModel, Column

from sqlalchemy import TIMESTAMP, func, Enum as SAEnum, UUID

class DocumentType(str, Enum):
    CHATBOT   = "chatbot"
    USER_INFO = "user_info"

class FileInfo(SQLModel, table=True):
    __tablename__ = "file_info"

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            default=uuid.uuid4,
            primary_key=True,
            index=True,
            nullable=False,
        )
    )

    email: str = Field(max_length=255, index=True)

    bot_name: str = Field(max_length=255)
    document_type: DocumentType = Field(
        sa_column=Column(
            SAEnum(DocumentType),
            default=DocumentType.CHATBOT,
            nullable=False,
        )
    )

    file_name: Optional[str] = Field(default=None, max_length=255)
    file_size: Optional[float] = Field(default=None)

    uploaded_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
            index=True
        )
    )

    last_accessed_at: Optional[datetime] = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=True,
            index=True,
            server_default=None,
        )
    )

    demo: Optional[str] = Field(default=None)
