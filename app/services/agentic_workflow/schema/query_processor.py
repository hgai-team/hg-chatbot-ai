from pydantic import BaseModel, Field
from typing import List, Dict, Any
from llama_index.core.llms import ChatMessage

class QueryProcessed(BaseModel):
    original_query: str
    sub_queries: List[str] = Field(default_factory=list)
    keywords_per_query: List[Dict[str, Any]] = Field(default_factory=list)
    history_messages: List[ChatMessage] = Field(default_factory=list)
    system_prompt: str
    instructions: str