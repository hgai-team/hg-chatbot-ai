import uuid

from typing import Optional, Dict, Any

from sqlmodel import Field, SQLModel, Column, JSON

from sqlalchemy import UUID

class UserInfo(SQLModel, table=True):
    __tablename__ = "user_info"

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            default=uuid.uuid4,
            primary_key=True,
            index=True,
            nullable=False,
        )
    )
    name: Optional[str] = Field(default=None, max_length=255, index=True)

    email: str = Field(max_length=255, index=True)

    managed_by: Optional[str] = Field(default=None, max_length=255, index=True)

    network_in_qlk: Optional[str] = Field(default=None, max_length=255, index=True)
    network_in_ys: Optional[str] = Field(default=None, max_length=255, index=True)
    project: Optional[str] = Field(default=None, max_length=255, index=True)

    department: Optional[str] = Field(default=None, max_length=255, index=True)

    metadata_: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
        alias="metadata",
    )
