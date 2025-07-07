from uuid import uuid4
from sqlmodel import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.schema import MasterData, MasterDataInput, UserInfo
from core.storages.client import PostgresEngineManager as PEM

from typing import List

async def create_master_data(
    input_: MasterDataInput,
):
    id_ = str(uuid4())
    async with PEM.get_session() as session:
        session.add(MasterData(
            id_=id_,
            type=input_.type,
            name=input_.name,
        ))

    return id_

async def get_all_master_data():
    async with PEM.get_session() as session:
        result = await session.exec(select(MasterData))
        return result.all()

async def update_master_data(
    input_: MasterData,
):
    async with PEM.get_session() as session:
        await session.exec(
            update(MasterData)
            .where(MasterData.id_ == input_.id_)
            .values(type=input_.type, name=input_.name)
        )

async def delete_master_data(
    id_: str,
):
    async with PEM.get_session() as session:
        await session.exec(
            delete(MasterData).where(MasterData.id_ == id_)
        )
    return {'status': 200}

async def delete_all_master_data():
    async with PEM.get_session() as session:
        await session.exec(delete(MasterData))
    return {'status': 200}

async def get_all_master_data_type(
    type: str,
):
    async with PEM.get_session() as session:
        result = await session.exec(
            select(MasterData).where(MasterData.type == type)
        )
        return result.all()

async def create_user_info(
    input_: List[UserInfo],
):
    async with PEM.get_session() as session:
        session.add_all(input_)

async def get_all_user_info():
    async with PEM.get_session() as session:
        result = await session.exec(select(UserInfo))
        return result.all()     
    
async def get_user_info(
    email: str
):
    async with PEM.get_session() as session:
        result = await session.exec(
            select(UserInfo).where(
                UserInfo.email==email
            )
        )
        return result.all()     
