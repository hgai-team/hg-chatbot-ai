import logging
logger = logging.getLogger(__name__)

from fastapi import (
    APIRouter, HTTPException, status,
    Depends, Body
)

from api.security import validate_auth

from api.schema import (
    DocumentType
)

from api.routers.bots.tools.files import get_files_info

app = APIRouter(
    prefix='/files',
    tags=["Files"]
)

@app.post(
    "",
    dependencies=[Depends(validate_auth)]
)
async def get_files_metadata(
    bot_name: list = Body(...),
    document_type: DocumentType = Body(None),
    q: str = Body(None),
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    file_ext: list[str] = Body([], description=".xlsx, .pdf, ..."),
    sort_field: str = Body(None),
    sort_order: int = Body(None, description="Sort order (Asc = 1, Desc = -1)"),
):
    try:
        resp = await get_files_info(
            bot_name=bot_name,
            document_type=document_type,
            q=q,
            limit=limit,
            page_index=page_index,
            file_ext=file_ext,
            sort_field=sort_field,
            sort_order=sort_order
        )
        return resp
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error in get_files_metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

