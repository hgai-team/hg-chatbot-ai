from sqlmodel import SQLModel, Field

class InfoPermissionInput(SQLModel):
    type: str = Field(max_length=100)
    name: str = Field(max_length=255)

class InfoPermission(InfoPermissionInput, table=True):
    id_ : str = Field(default=None, primary_key=True)
    type: str = Field(max_length=100)
    name: str = Field(max_length=255)
