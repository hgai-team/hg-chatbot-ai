import logging
logger = logging.getLogger(__name__)

import asyncio
import torch, gc

from typing import List, Tuple, Optional
from sentence_transformers import CrossEncoder

from .base import BaseReranker

class MSMarcoReranker(BaseReranker):
    _model_name: str = 'cross-encoder/ms-marco-MiniLM-L6-v2'
    _model: Optional[CrossEncoder] = None

    _predict_lock = asyncio.Semaphore(1)

    @classmethod
    async def rerank(
        cls,
        query: str,
        docs: List[dict],
        model_name: Optional[str] = None
    ) -> List[Tuple[str, float]]:

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required but not available")

        name = model_name or cls._model_name

        if cls._model is None or (model_name and name != cls._model_name):
            if cls._model is not None:
                try:
                    cls._model.to('cpu')
                except Exception:
                    pass
                del cls._model
                torch.cuda.empty_cache()
                gc.collect()

            logger.info(f"Init rerank model: {name}")
            cls._model = CrossEncoder(name, device='cuda')
            cls._model.eval()
            cls._model_name = name

        passages = []
        for idx in range(len(docs)):
            doc: dict = docs[idx]
            passages.append(doc["text"])
            if 'original_content' in doc['metadata']:
                doc["text"] = doc['metadata']['original_content']
            doc.pop('metadata')

        inputs = [[query, passage] for passage in passages]

        async with cls._predict_lock:
            def _predict():
                with torch.no_grad():
                    return cls._model.predict(inputs)
            raw_scores = await asyncio.to_thread(_predict)

        scores: List[float] = [float(s) for s in raw_scores]

        ranked: List[Tuple[str, float]] = sorted(
            zip(docs, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return ranked

