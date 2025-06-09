from fastapi import APIRouter, Depends
from sqlmodel import create_engine, Session, SQLModel

from api.routers import (
    vahacha_files_router,
    vahacha_chatbots_router,
    vahacha_agent_evaluations_router,
    vahacha_retrieval_evaluations_router,
    vahacha_info_permission_router,

    auth_router,
    history_router,
    tokenizer_router,
)

from api.security import validate_auth
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
    dependencies=[Depends(validate_auth)],
)
def health_check():
    return {"status": 200}



app.include_router(vahacha_files_router)
app.include_router(vahacha_chatbots_router)
app.include_router(vahacha_agent_evaluations_router)
app.include_router(vahacha_retrieval_evaluations_router)
app.include_router(vahacha_info_permission_router)

app.include_router(auth_router)
app.include_router(history_router)
app.include_router(tokenizer_router)


