from pydantic import BaseModel
from typing import Any

class BaseResponse(BaseModel):
    status: int
    data: Any
