import logging
logger = logging.getLogger(__name__)

import asyncio

from typing import List, Tuple, Optional
from sentence_transformers import CrossEncoder

from .base import BaseReranker

class MSMarcoReranker(BaseReranker):
    _model_name: str = 'cross-encoder/ms-marco-MiniLM-L6-v2'
    _model: Optional[CrossEncoder] = None

    @classmethod
    async def rerank(
        cls,
        query: str,
        docs: List[dict],
        model_name: Optional[str] = None
    ) -> List[Tuple[str, float]]:

        name = model_name or cls._model_name

        if cls._model is None or (model_name and name != cls._model_name):
            logger.info(f"Init rerank model: {name}")
            cls._model = CrossEncoder(name, device='cuda')
            cls._model_name = name

        passages = []
        for idx in range(len(docs)):
            doc: dict = docs[idx]
            passages.append(doc["text"])
            if 'original_content' in doc['metadata']:
                doc["text"] = doc['metadata']['original_content']
            doc.pop('metadata')

        inputs = [[query, passage] for passage in passages]

        raw_scores = await asyncio.to_thread(cls._model.predict, inputs)

        scores: List[float] = [float(s) for s in raw_scores]

        ranked: List[Tuple[str, float]] = sorted(
            filter(lambda x: x[1] > 1, zip(docs, scores)),
            key=lambda x: x[1],
            reverse=True
        )

        return ranked

