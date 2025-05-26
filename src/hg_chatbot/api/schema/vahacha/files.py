from pydantic import BaseModel, Field

class FilesResponse(BaseModel):
    status: int = Field(200)
