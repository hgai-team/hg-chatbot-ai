from pydantic import BaseModel
from typing import Any

class FileResponse(BaseModel):
    status: int
