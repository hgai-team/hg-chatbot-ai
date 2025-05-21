from typing import Annotated

from fastapi.security import APIKeyHeader
from fastapi import HTTPException, Security, Depends

from starlette.status import HTTP_403_FORBIDDEN

from api.config import APISettings, get_api_settings

async def get_api_key(
    *, api_key_header: str = Security(APIKeyHeader(name="X-API-Key", auto_error=False)), settings: Annotated[APISettings, Depends(get_api_settings)]
):
    """
    Xác thực API Key được truyền trong header.
    """
    if api_key_header == settings.API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate API KEY"
    )


