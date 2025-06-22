from sqlmodel import SQLModel, Field
from .base import BaseResponse
from typing import List

class MasterDataInput(SQLModel):
    type: str = Field(max_length=100)
    name: str = Field(max_length=255)

class MasterData(MasterDataInput, table=True):
    id_ : str = Field(default=None, primary_key=True)

class MasterDataResponse(BaseResponse):
    data: List[MasterData]
