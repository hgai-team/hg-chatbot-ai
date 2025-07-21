from uuid import uuid4
from sqlmodel import select, update, delete

from api.schema import (
    UserInfo,
)
from core.storages.client import PostgresEngineManager as PEM

from typing import List

# User Info

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

async def aggregated_user_info(
    email: str
):
    data = await get_user_info(email=email)

    fields = ['network_in_ys', 'department', 'network_in_qlk', 'project']

    aggregated = {
        field: list({
            getattr(user, field)
            for user in data
            if getattr(user, field) is not None
        })
        for field in fields
    }

    return aggregated
