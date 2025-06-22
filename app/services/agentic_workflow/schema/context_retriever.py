from pydantic import BaseModel, Field
from typing import Dict, Any

class ContextRetrieved(BaseModel):
    context_string: str
    source_documents: Dict[str, Dict[str, Any]] = Field(default_factory=dict)