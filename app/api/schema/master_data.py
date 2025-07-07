import uuid

from .base import BaseResponse

from typing import List, Optional, Dict, Any

from sqlmodel import Field, SQLModel, Column, JSON

class MasterDataInput(SQLModel):
    type: str = Field(max_length=100)
    name: str = Field(max_length=255)

class MasterData(MasterDataInput, table=True):
    id_ : str = Field(default=None, primary_key=True)

class MasterDataResponse(BaseResponse):
    data: List[MasterData]

class UserInfo(SQLModel, table=True):
    __tablename__ = "user_info"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, 
        primary_key=True, 
        index=True
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