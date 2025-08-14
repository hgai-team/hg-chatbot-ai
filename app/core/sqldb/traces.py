from sqlmodel import Field, SQLModel, JSON, Column
from pydantic import BaseModel, ConfigDict
from sqlalchemy import TIMESTAMP

from typing import Any, Dict, Optional

import uuid
import datetime

class TraceSpan(SQLModel, table=True):
    model_config = ConfigDict(validate_by_name=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    trace_id: uuid.UUID = Field(index=True)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="tracespan.id")
    name: str = Field(index=True)
    span_type: str = Field(index=True, default="DEFAULT")
    status: str = Field(default="OK", index=True)
    start_time: datetime.datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            index=True
        )
    )
    end_time: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            index=True
        )
    )
    metadata_: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
        alias="metadata",
    )


class SpanBase(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    name: str
    span_type: str = "DEFAULT"
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    status: str = "OK"

    metadata_: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON),
        alias="metadata",
    )

class SpanCreate(SpanBase):
    id: uuid.UUID
    trace_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None

# class Span(SpanBase):
#     id: uuid.UUID
#     trace_id: uuid.UUID
#     parent_id: Optional[uuid.UUID] = None

#     class Config:
#         from_attributes = True

# class TraceSummary(BaseModel):
#     trace_id: uuid.UUID
#     root_span_name: str
#     status: str
#     start_time: datetime.datetime
#     duration_ms: Optional[float]
#     total_spans: int

# def _safe_serialize(data: Any) -> Optional[str]:
#     """Serialize dữ liệu thành chuỗi JSON một cách an toàn."""
#     if data is None:
#         return None
#     try:
#         if hasattr(data, 'model_dump_json'):
#             return data.model_dump_json(indent=2)

#         return json.dumps(data, indent=2, default=str)
#     except (TypeError, OverflowError):
#         return repr(data)
