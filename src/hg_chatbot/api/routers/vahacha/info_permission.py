from uuid import uuid4
from fastapi import (
    APIRouter,
    Path,
    Depends
)
from sqlmodel import (
    Session,
    select,
    create_engine,
    update,
    delete
)

from api.security import validate_auth
from api.schema import vahacha_InfoPermissionInput, vahacha_InfoPermission
from services import get_settings_cached

def get_session():
    engine = create_engine(
        get_settings_cached().SQL_DB_PATH,
        echo=True,
        connect_args={"check_same_thread": False}
    )
    return Session(engine)

app = APIRouter(
    prefix="/vahacha/info-permission",
    tags=["Info Permission"]
)

@app.post(
    "/create",
    dependencies=[Depends(validate_auth)]
)
async def create_data(
    input_: vahacha_InfoPermissionInput,
):
    input_dict = input_.model_dump()

    with get_session() as session:
        session.add(vahacha_InfoPermission(
            id_=str(uuid4()),
            type=input_dict['type'],
            name=input_dict['name'],
        ))
        session.commit()

    return {'status': 200}

@app.post(
    "/get-all",
    dependencies=[Depends(validate_auth)]
)
async def get_all_data():

    with get_session() as session:
        info = session.exec(select(vahacha_InfoPermission)).all()

    return {
        'results': info,
        'status': 200
    }

@app.post(
    "/get-all/{type}",
    dependencies=[Depends(validate_auth)]
)
async def get_all_type_data(
    type: str = Path(...)
):

    with get_session() as session:
        info = session.exec(select(vahacha_InfoPermission).where(vahacha_InfoPermission.type==type)).all()

    return {
        'results': info,
        'status': 200
    }

@app.post(
    "/update",
    dependencies=[Depends(validate_auth)]
)
async def update_data(
    input_: vahacha_InfoPermission
):
    input_dict = input_.model_dump()

    with get_session() as session:
        session.exec(
            update(vahacha_InfoPermission).where(vahacha_InfoPermission.id_==input_dict['id_']).values(
                type=input_dict['type'],
                name=input_dict['name']
            )
        )
        session.commit()

    return {
        'status': 200
    }

@app.delete(
    "/delete",
    dependencies=[Depends(validate_auth)]
)
async def delete_data(
    id_: str
):
    with get_session() as session:
        session.exec(
            delete(vahacha_InfoPermission).where(vahacha_InfoPermission.id_==id_)
        )
        session.commit()

    return {
        'status': 200
    }

@app.delete(
    "/delete",
    dependencies=[Depends(validate_auth)]
)
async def delete_data(
    id_: str
):
    with get_session() as session:
        session.exec(
            delete(vahacha_InfoPermission).where(vahacha_InfoPermission.id_==id_)
        )
        session.commit()

    return {
        'status': 200
    }

@app.delete(
    "/delete-all",
    dependencies=[Depends(validate_auth)]
)
async def delete_all_data():
    with get_session() as session:
        session.exec(
            delete(vahacha_InfoPermission)
        )
        session.commit()

    return {
        'status': 200
    }
