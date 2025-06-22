from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel, JSON, Column
from pydantic import BaseModel
import datetime
import uuid

class TraceSpan(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    trace_id: uuid.UUID = Field(index=True)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="tracespan.id")
    name: str = Field(index=True)
    span_type: str = Field(index=True, default="DEFAULT")
    status: str = Field(default="OK", index=True)
    start_time: datetime.datetime = Field(index=True)
    end_time: Optional[datetime.datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class SpanBase(BaseModel):
    name: str
    span_type: str = "DEFAULT"
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    metadata: Dict[str, Any] = {}
    status: str = "OK"

class SpanCreate(SpanBase):
    id: uuid.UUID
    trace_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None

class Span(SpanBase):
    id: uuid.UUID
    trace_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True

class TraceSummary(BaseModel):
    trace_id: uuid.UUID
    root_span_name: str
    status: str
    start_time: datetime.datetime
    duration_ms: Optional[float]
    total_spans: int
