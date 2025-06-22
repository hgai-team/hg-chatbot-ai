from uuid import uuid4
from sqlmodel import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.schema import MasterData, MasterDataInput
from core.storages.client import PostgresEngineManager

async def create_master_data(
    input_: MasterDataInput,
):
    id_ = str(uuid4())
    async with PostgresEngineManager.get_session() as session:        
        session.add(MasterData(
            id_=id_,
            type=input_.type,
            name=input_.name,
        ))

    return id_

async def get_all_master_data():
    async with PostgresEngineManager.get_session() as session:
        result = await session.execute(select(MasterData))
        return result.scalars().all()

async def update_master_data(
    input_: MasterData,
):
    async with PostgresEngineManager.get_session() as session:
        await session.execute(
            update(MasterData)
            .where(MasterData.id_ == input_.id_)
            .values(type=input_.type, name=input_.name)
        )

async def delete_master_data(
    id_: str,
):
    async with PostgresEngineManager.get_session() as session:
        await session.execute(
            delete(MasterData).where(MasterData.id_ == id_)
        )
    return {'status': 200}

async def delete_all_master_data():
    async with PostgresEngineManager.get_session() as session:
        await session.execute(delete(MasterData))
    return {'status': 200}

async def get_all_master_data_type(
    type: str,
):
    async with PostgresEngineManager.get_session() as session:
        result = await session.execute(
            select(MasterData).where(MasterData.type == type)
        )
        return result.scalars().all()
