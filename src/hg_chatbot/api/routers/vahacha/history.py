from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Path,
    Form
)

from api.schema import BotNames

from api.security import validate_auth

from services import (
    get_mongodb_memory_store
)

app = APIRouter(
    prefix="/history",
    tags=["History"]
)

@app.get(
    "/session",
    dependencies=[Depends(validate_auth)],
)
async def get_session_history(
    user_id: str,
    session_id: str,
    bot_name: BotNames,
):

    memory_store = get_mongodb_memory_store(
        database_name=bot_name,
        collection_name=bot_name,
    )

    try:
        history = memory_store.get_session_history(
            user_id=user_id,
            session_id=session_id,
        )
        return {
            'results': history.history,
            'session_title': history.session_title
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post(
    "/session/rating",
    dependencies=[Depends(validate_auth)],
)
async def add_rating(
    chat_id: str,
    rating_type: str,
    rating_text: str,
    bot_name: BotNames,
):

    memory_store = get_mongodb_memory_store(
        database_name=bot_name,
        collection_name=bot_name,
    )

    try:
        memory_store.add_rating(
            chat_id=chat_id,
            rating_type=rating_type,
            rating_text=rating_text
        )
        return {
            "status": 200
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# @app.get(
#     "/sessions",
#     dependencies=[Depends(validate_auth)],
# )
# async def get_user_sessions(
#     user_id: str,
#     bot_name: BotNames,
# ):

#     memory_store = get_mongodb_memory_store(
#         database_name=bot_name,
#         collection_name=bot_name,
#     )

#     try:
#         history = memory_store.get_user_sessions(
#             user_id=user_id
#         )
#         return {
#             'results': history
#         }
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )

