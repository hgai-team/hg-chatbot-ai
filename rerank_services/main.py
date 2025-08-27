from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager
import logging
import asyncio
import torch
import gc
import os
from sentence_transformers import CrossEncoder

# --------------------------
# Config (có thể đổi qua env)
# --------------------------
REQUIRE_GPU = os.getenv("RERANK_REQUIRE_GPU", "0") == "1"  # 1: bắt buộc CUDA
PREDICT_CONCURRENCY = int(os.getenv("RERANK_PREDICT_CONCURRENCY", "1"))
DEFAULT_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
DEFAULT_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "8"))
PRELOAD_MODEL = os.getenv("RERANK_PRELOAD", True)   # 1: preload ở startup

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Document(BaseModel):
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RerankRequest(BaseModel):
    query: str
    docs: List[Document]
    model_name: Optional[str] = None
    top_k: Optional[int] = None
    batch_size: Optional[int] = None

class RerankedItem(BaseModel):
    doc: Dict[str, Any]
    score: float

class RerankResponse(BaseModel):
    results: List[RerankedItem]

class MSMarcoReranker:
    _model_name: str = DEFAULT_MODEL
    _model: Optional[CrossEncoder] = None
    _device: str = "cpu"
    _model_lock = asyncio.Lock()                 # bảo vệ load/cleanup model
    _predict_sem = asyncio.Semaphore(PREDICT_CONCURRENCY)

    @classmethod
    def _select_device(cls) -> str:
        if torch.cuda.is_available():
            return "cuda"
        if REQUIRE_GPU:
            raise RuntimeError("CUDA GPU is required but not available")
        return "cpu"

    @classmethod
    def _need_cleanup_due_to_memory(cls) -> bool:
        if not torch.cuda.is_available():
            return False
        try:
            free, total = torch.cuda.mem_get_info()
            # dọn khi còn <20% VRAM
            return (free / total) < 0.20
        except Exception:
            return False

    @classmethod
    def _cleanup_model(cls):
        if cls._model is not None:
            try:
                if hasattr(cls._model, "to"):
                    cls._model.to("cpu")
            except Exception:
                pass
            del cls._model
            cls._model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

    @classmethod
    async def _ensure_model(cls, name: str):
        """
        Đảm bảo model đúng tên đã được load và sẵn sàng.
        Khóa bằng _model_lock để tránh race khi (re)load.
        """
        async with cls._model_lock:
            if (cls._model is None) or (name != cls._model_name):
                if cls._need_cleanup_due_to_memory():
                    logger.warning("Low GPU memory; cleaning up before (re)loading model.")
                    cls._cleanup_model()

                cls._cleanup_model()
                cls._device = cls._select_device()
                logger.info(f"Loading rerank model: {name} on device={cls._device}")
                cls._model = CrossEncoder(name, device=cls._device)
                cls._model.eval()
                cls._model_name = name

    @classmethod
    async def rerank(
        cls,
        query: str,
        docs: List[Document],
        model_name: Optional[str] = None,
        top_k: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> List[RerankedItem]:

        if not docs:
            return []

        name = model_name or cls._model_name
        await cls._ensure_model(name)

        # chuẩn bị inputs cho scoring (ưu tiên original_content nếu có)
        passages: List[str] = []
        outputs: List[Dict[str, Any]] = []
        for doc in docs:
            used_text = doc.metadata.get("original_content", doc.text)
            passages.append(used_text)
            # Trả ra text gốc để client hiển thị (có thể giữ/loại metadata tùy yêu cầu)
            outputs.append({"text": doc.text, "metadata": doc.metadata})

        inputs = [[query, p] for p in passages]

        bs = batch_size or DEFAULT_BATCH_SIZE
        async with cls._predict_sem:
            def _predict():
                with torch.no_grad():
                    return cls._model.predict(
                        inputs, batch_size=bs, show_progress_bar=False
                    )
            raw_scores = await asyncio.to_thread(_predict)

        scores = [float(s) for s in raw_scores]
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        if top_k is not None and top_k > 0:
            ranked_idx = ranked_idx[:min(top_k, len(ranked_idx))]
        return [RerankedItem(doc=outputs[i], score=scores[i]) for i in ranked_idx]

# --------------------------
# FastAPI app with lifespan
# --------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Chọn device sớm để health check có giá trị ngay
        MSMarcoReranker._device = MSMarcoReranker._select_device()

        # Tuỳ chọn: preload model để tránh latency request đầu
        if PRELOAD_MODEL:
            await MSMarcoReranker._ensure_model(DEFAULT_MODEL)
            logger.info("Model preloaded successfully.")
        yield
    finally:
        # Shutdown: cleanup tài nguyên
        MSMarcoReranker._cleanup_model()
        logger.info("Service shutdown completed (lifespan).")

app = FastAPI(
    title="Reranker Service",
    version="1.1.0",
    lifespan=lifespan,   # <-- dùng lifespan thay cho on_event
)

# --------------------------
# Routes
# --------------------------
@app.get("/health")
async def health_check():
    cuda_available = torch.cuda.is_available()
    device = "cuda" if cuda_available else "cpu"
    free = total = None
    if cuda_available:
        try:
            free, total = torch.cuda.mem_get_info()
        except Exception:
            pass
    return {
        "status": "healthy",
        "cuda_available": cuda_available,
        "device": device,
        "model_loaded": MSMarcoReranker._model is not None,
        "model_name": MSMarcoReranker._model_name,
        "gpu_mem_free": free,
        "gpu_mem_total": total,
    }

@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    try:
        results = await MSMarcoReranker.rerank(
            query=request.query,
            docs=request.docs,
            model_name=request.model_name,
            top_k=request.top_k,
            batch_size=request.batch_size,
        )
        return RerankResponse(results=results)
    except RuntimeError as e:
        # ví dụ thiếu GPU khi REQUIRE_GPU=True
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Reranking failed")
        raise HTTPException(status_code=500, detail="Internal error")

@app.get("/")
async def root():
    return {"message": "Reranker Service is running"}
