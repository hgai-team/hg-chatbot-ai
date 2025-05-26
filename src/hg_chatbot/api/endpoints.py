from fastapi import APIRouter, Depends
from sqlmodel import create_engine, Session, SQLModel

from api.routers import (
    vahacha_files_router,
    vahacha_chatbots_router,
    vahacha_tokenizer_router,
    vahacha_agent_evaluations_router,
    vahacha_retrieval_evaluations_router,
    vahacha_history_router,
    vahacha_info_permission
)

from api.security import get_api_key
from api.schema import vahacha_InfoPermission
from services import get_settings_cached

def create_db_and_tables():
    engine = create_engine(
        get_settings_cached().SQL_DB_PATH,
        echo=True,
        connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

app = APIRouter(
    prefix="/api/v1",
)

@app.get(
    "/",
    dependencies=[Depends(get_api_key)],
)
def health_check():
    return {"status": 200}

app.include_router(vahacha_files_router)
app.include_router(vahacha_chatbots_router)
app.include_router(vahacha_tokenizer_router)
app.include_router(vahacha_agent_evaluations_router)
app.include_router(vahacha_retrieval_evaluations_router)
app.include_router(vahacha_history_router)
app.include_router(vahacha_info_permission)
