import uuid
import pandas as pd

from fastapi import APIRouter, Depends, Path, UploadFile, HTTPException

from io import BytesIO

from api.security import validate_auth
from api.schema import MasterDataInput, MasterDataResponse, MasterData, BaseResponse, UserInfo

from .ops_bot.handlers.master_data import (
    create_master_data,
    get_all_master_data,
    update_master_data,
    delete_master_data,
    delete_all_master_data,
    get_all_master_data_type,
    create_user_info,
    get_all_user_info,
    get_user_info,
    aggregated_user_info
)


app = APIRouter(
    prefix="/bots/VaHaCha",
    tags=["VaHaCha Data"]
)

@app.post(
    "/master-data",
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
    "/master-data",
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
    "/master-data/{type}",
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
    "/master-data",
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
    "/master-data",
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

@app.post(
    "/user-infos",
    dependencies=[Depends(validate_auth)]
)
async def upload_user_info(
    file: UploadFile,
):
    if file.content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        raise HTTPException(
            status_code=400,
            detail="Định dạng file không hợp lệ. Vui lòng tải lên file .xlsx."
        )
        
    contents = await file.read()

    with BytesIO(contents) as buffer:
        df = pd.read_excel(buffer)

    df.columns = [col.lower() for col in df.columns.tolist()]
     
    users = []

    df = df.where(pd.notna(df), None)
    for _, row in df.iterrows():
        if row.get("mail nhân sự") and isinstance(row.get("mail nhân sự"), str):
            def get_lower_str_or_none(value):
                if isinstance(value, str):
                    stripped_value = value.strip()
                    if stripped_value == '':
                        return None
                    return stripped_value.lower()
                return None 

            def get_bool_from_excel(value):
                if value is None or value == '':
                    return False
                try:
                    num_value = float(value)
                    return num_value == 1.0
                except (ValueError, TypeError):
                    return False

            user_data = {}
            user_data["id"] = uuid.uuid4() 
            
            user_data["name"] = get_lower_str_or_none(row.get("tên nhân sự"))
            user_data["email"] = get_lower_str_or_none(row.get("mail nhân sự"))
            user_data["managed_by"] = get_lower_str_or_none(row.get("quản lý"))
            user_data["network_in_qlk"] = get_lower_str_or_none(row.get("tên net trên tool qlk"))
            user_data["network_in_ys"] = get_lower_str_or_none(row.get("tên net (theo youtube studio)"))
            user_data["project"] = get_lower_str_or_none(row.get("tên dự án"))
            user_data["department"] = get_lower_str_or_none(row.get("phòng ban"))
            
            user_data["metadata_"] = {
                'tên dự án': get_lower_str_or_none(row.get("tên dự án")),
                'quy_định_chung': get_bool_from_excel(row.get("quy_định_chung")),
                'quy_định_chung_dự_án': get_bool_from_excel(row.get("quy_định_chung_dự_án")),
                'file_xlcv_chung_dự_án': get_bool_from_excel(row.get("file_xlcv_chung_dự_án")),
                'quy_định_riêng_dự_án_phòng_ban': get_bool_from_excel(row.get("quy_định_riêng_dự_án_phòng_ban")),
                'file_xlcv_riêng_dự_án_phòng_ban': get_bool_from_excel(row.get("file_xlcv_riêng_dự_án_phòng_ban")),
                'quy_định_riêng_dự_án_net': get_bool_from_excel(row.get("quy_định_riêng_dự_án_net")),
                'file_xlcv_riêng_dự_án_net': get_bool_from_excel(row.get("file_xlcv_riêng_dự_án_net")),
                'quy_định_network': get_bool_from_excel(row.get("quy_định_network")),
            }
            
            users.append(UserInfo.model_validate(user_data))
    
    if users:
        await create_user_info(input_=users)
    
    return {'status': 200}

@app.get(
    "/user-infos",
    dependencies=[Depends(validate_auth)],
)
async def get_all_user():
    data = await get_all_user_info()

    return {
        "status": 200,
        "data": data
    }
    
@app.get(
    "/user-info",
    dependencies=[Depends(validate_auth)],
)
async def get_user(
    email: str
):
    data = await get_user_info(email=email)

    return {
        "status": 200,
        "data": data
    }

@app.get(
    "/user-info/aggregated",
    dependencies=[Depends(validate_auth)],
)
async def get_aggregated_user_info(
    email: str
):
    data = await aggregated_user_info(email=email)

    return {
        "status": 200,
        "data": data
    }