from fastapi import APIRouter, Depends, Path

from api.security import validate_auth
from api.schema import MasterDataInput, MasterDataResponse, MasterData, BaseResponse

from .ops_bot.handlers.master_data import (
    create_master_data,
    get_all_master_data,
    update_master_data,
    delete_master_data,
    delete_all_master_data,
    get_all_master_data_type
)


app = APIRouter(
    prefix="/bots/VaHaCha/master-data",
    tags=["VaHaCha Master Data"]
)

@app.post(
    "",
    response_model=MasterDataResponse,
    dependencies=[Depends(validate_auth)]
)
async def create_data(
    input_: MasterDataInput,
):
    id_ = await create_master_data(input_)

    return MasterDataResponse(
        status=200,
        data=[MasterData(
            id_=id_,
            type=input_.type,
            name=input_.name
        )]
    )

@app.get(
    "",
    dependencies=[Depends(validate_auth)],
    response_model=MasterDataResponse,
)
async def get_all_data():
    data = await get_all_master_data()

    return MasterDataResponse(
        status=200,
        data=data
    )

@app.get(
    "/{type}",
    response_model=MasterDataResponse,
    dependencies=[Depends(validate_auth)]
)
async def get_all_type_data(
    type: str = Path(...)
):
    data = await get_all_master_data_type(type)

    return MasterDataResponse(
        status=200,
        data=data
    )

@app.put(
    "",
    response_model=MasterDataResponse,
    dependencies=[Depends(validate_auth)]
)
async def update_data(
    input_: MasterData
):
    await update_master_data(input_)
    return MasterDataResponse(
        status=200,
        data=[input_]
    )

@app.delete(
    "",
    response_model=BaseResponse,
    dependencies=[Depends(validate_auth)]
)
async def delete_data(
    id_: str
):
    await delete_master_data(id_)

    return BaseResponse(
        status=200,
        data={
            'id': id_
        }
    )
