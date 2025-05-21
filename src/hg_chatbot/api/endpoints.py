from fastapi import APIRouter, Depends

from api.routers import (
    files_router,
    chatbots_router,
    tokenizer_router,
    agent_evaluations_router,
    retrieval_evaluations_router,
)

from api.security import get_api_key

app = APIRouter(
    prefix="/api/v1",
)

@app.get(
    "/",
    dependencies=[Depends(get_api_key)],
)
def health_check():
    return {"status": 200}

app.include_router(files_router)
app.include_router(chatbots_router)
app.include_router(tokenizer_router)
app.include_router(agent_evaluations_router)
app.include_router(retrieval_evaluations_router)
