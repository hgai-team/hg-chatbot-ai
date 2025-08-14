from pydantic import BaseModel
from typing import Any
from enum import Enum
class FileResponse(BaseModel):
    status: int
