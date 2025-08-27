import logging
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

from .base import BaseReranker
from api.config import get_api_settings

def serialize_datetime_objects(obj):
    """Recursively convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    else:
        return obj

class MSMarcoReranker(BaseReranker):
    base_url = "http://msmarco-hg-chatbot:28889" if get_api_settings().ENV == "dev" else "http://msmarco-hg-chatbot:18889"
    
    @classmethod
    async def health_check(cls):
        """Check service health"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{cls.base_url}/health")
            return response.json()
    
    @classmethod
    async def rerank(cls, query: str, docs: list, model_name: str = None):
        """Rerank documents"""
        # Serialize datetime objects in docs
        serialized_docs = serialize_datetime_objects(docs)
        
        payload = {
            "query": query,
            "docs": serialized_docs,
            "model_name": model_name
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cls.base_url}/rerank",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()["results"]
            else:
                raise Exception(f"Request failed: {response.status_code} - {response.text}")