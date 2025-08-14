from typing import Optional, Any, List, Dict
from uuid import uuid4, UUID

from sqlmodel import (
    func,
    select, update, delete, asc, desc
)

from sqlalchemy.dialects.postgresql import insert

from core.sqldb.user_info import (
    UserInfo,
)
from core.storages.client import PostgresEngineManager as PEM

# User Info
async def upsert_userinfo(
    input_: List[UserInfo],
):
    if not input_:
        return

    async with PEM.get_session() as session:
        values_to_upsert = []
        for user_info in input_:
            values_to_upsert.append({
                'id': user_info.id or uuid4(),
                'name': str(user_info.name).lower() if user_info.name else user_info.name,
                'email': str(user_info.email).lower() if user_info.email else user_info.email,
                'managed_by': str(user_info.managed_by).lower() if user_info.managed_by else user_info.managed_by,
                'network_in_qlk': str(user_info.network_in_qlk).lower() if user_info.network_in_qlk else user_info.network_in_qlk,
                'network_in_ys': str(user_info.network_in_ys).lower() if user_info.network_in_ys else user_info.network_in_ys,
                'project': str(user_info.project).lower() if user_info.project else user_info.project,
                'department': str(user_info.department).lower() if user_info.department else user_info.department,
                'metadata': user_info.metadata_,
            })

        stmt = insert(UserInfo.__table__).values(values_to_upsert)

        update_dict = {
            'name': stmt.excluded.name,
            'managed_by': stmt.excluded.managed_by,
            'network_in_qlk': stmt.excluded.network_in_qlk,
            'network_in_ys': stmt.excluded.network_in_ys,
            'project': stmt.excluded.project,
            'department': stmt.excluded.department,
            'metadata': stmt.excluded.metadata,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_=update_dict
        )

        await session.exec(stmt)

async def create_user_info(
    input_: List[UserInfo],
):
    async with PEM.get_session() as session:
        session.add_all(input_)

async def update_user_info(
    input_: List[UserInfo],
):
    async with PEM.get_session() as session:
        update_data = []
        for user_info in input_:
            update_data.append({
                'id': user_info.id,
                'name': str(user_info.name).lower() if user_info.name else user_info.name,
                'email': str(user_info.email).lower() if user_info.email else user_info.email,
                'managed_by': str(user_info.managed_by).lower() if user_info.managed_by else user_info.managed_by,
                'network_in_qlk': str(user_info.network_in_qlk).lower() if user_info.network_in_qlk else user_info.network_in_qlk,
                'network_in_ys': str(user_info.network_in_ys).lower() if user_info.network_in_ys else user_info.network_in_ys,
                'project': str(user_info.project).lower() if user_info.project else user_info.project,
                'department': str(user_info.department).lower() if user_info.department else user_info.department,
                'metadata_': user_info.metadata_,
            })

        await session.run_sync(
            lambda sync_session: sync_session.bulk_update_mappings(
                UserInfo, update_data
            )
        )

async def delete_user_info(
    input_: List[UUID],
):
    async with PEM.get_session() as session:
        stmt = delete(UserInfo).where(UserInfo.id.in_(input_))
        await session.exec(stmt)

async def get_unique_values(
    column_name: str,
    filters: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
    async with PEM.get_session() as session:
        column = getattr(UserInfo, column_name)

        stmt = select(column).distinct().where(column.is_not(None))

        if filters:
            for filter_config in filters:
                field = filter_config.get("field")
                operator = filter_config.get("operator", "eq")
                value = filter_config.get("value")

                if not hasattr(UserInfo, field) or field in ['metadata_']:
                    continue

                field_attr = getattr(UserInfo, field)

                if operator == "eq":
                    stmt = stmt.where(field_attr == value)
                elif operator == "ne":
                    stmt = stmt.where(field_attr != value)
                elif operator == "like":
                    stmt = stmt.where(field_attr.like(value))
                elif operator == "in":
                    stmt = stmt.where(field_attr.in_(value))
                elif operator == "gt":
                    stmt = stmt.where(field_attr > value)
                elif operator == "gte":
                    stmt = stmt.where(field_attr >= value)
                elif operator == "lt":
                    stmt = stmt.where(field_attr < value)
                elif operator == "lte":
                    stmt = stmt.where(field_attr <= value)

        result = await session.exec(stmt)

        return result.all()

async def search_user_infos(
    limit: int,
    page_index: int,
    sort_field: str,
    sort_order: int,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """
    Advanced version with support for multiple filter operators

    Args:
        filters: List of filter dictionaries with format:
                [{"field": "status", "operator": "eq", "value": "OK"},
                 {"field": "name", "operator": "like", "value": "%test%"}]

    Supported operators: eq, ne, like, in, gt, gte, lt, lte
    """
    async with PEM.get_session() as session:
        query = select(UserInfo)

        if filters:
            for filter_config in filters:
                field = filter_config.get("field")
                operator = filter_config.get("operator", "eq")
                value = filter_config.get("value")

                if not hasattr(UserInfo, field) or field in ['metadata_']:
                    continue

                field_attr = getattr(UserInfo, field)

                if operator == "eq":
                    query = query.where(field_attr == value)
                elif operator == "ne":
                    query = query.where(field_attr != value)
                elif operator == "like":
                    query = query.where(field_attr.like(value))
                elif operator == "in":
                    query = query.where(field_attr.in_(value))
                elif operator == "gt":
                    query = query.where(field_attr > value)
                elif operator == "gte":
                    query = query.where(field_attr >= value)
                elif operator == "lt":
                    query = query.where(field_attr < value)
                elif operator == "lte":
                    query = query.where(field_attr <= value)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count_result = await session.exec(count_query)
        total_count = total_count_result.one()

        if total_count == 0:
            return {
                "items": [],
                "total_items": 0,
                "total_pages": 0,
                "page_index": page_index,
            }

        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

        if page_index > total_pages and total_pages >= 0:
            raise ValueError(f"page_index ({page_index}) cannot be greater than to total pages ({total_pages})")

        # Apply sorting
        if sort_field:
            if hasattr(UserInfo, sort_field) and sort_field not in ['metadata_']:
                field_attr = getattr(UserInfo, sort_field)
                if sort_order == 1:
                    query = query.order_by(asc(field_attr))
                elif sort_order == -1:
                    query = query.order_by(desc(field_attr))

        # Apply pagination
        offset = (page_index - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await session.exec(query)
        user_infos = result.all()

        return {
            "items": user_infos,
            "total_items": total_count,
            "total_pages": total_pages,
            "page_index": page_index
        }

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
