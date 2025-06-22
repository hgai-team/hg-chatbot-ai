from fastapi import APIRouter, Depends

from api.security import validate_auth, get_public_key

app = APIRouter(
    prefix='/auth',
    tags=["Auth"]
)

@app.get(
    "/cert",
    dependencies=[Depends(validate_auth)]
)
async def fetch_cert(
    token: str
):
    return {
        "public_key": await get_public_key(token=token)
    }

