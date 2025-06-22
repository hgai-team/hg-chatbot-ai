import jwt
from jwt import PyJWKClient, DecodeError
from cryptography.hazmat.primitives import serialization

from functools import lru_cache
from typing import Annotated

from fastapi import HTTPException, Depends, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from api.config import APISettings, get_api_settings

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme  = HTTPBearer(auto_error=False)

async def get_api_key(
    *,
    api_key_header: str = Security(api_key_scheme),
    settings: Annotated[APISettings, Depends(get_api_settings)],
):
    if api_key_header == settings.API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="Could not validate API KEY"
    )

async def get_public_key(
    token: str,
):
    settings = get_api_settings()

    if settings.ENV == 'pro':
        jwks_client = PyJWKClient(settings.JWKS_HG_APP_URL)
        issuer = settings.JWT_ISSUER_HG_APP
    elif settings.ENV == 'dev':
        jwks_client = PyJWKClient(settings.JWKS_HG_DEV_URL)
        issuer = settings.JWT_ISSUER_HG_DEV

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
    except DecodeError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Malformed JWT (not enough segments)")

    try:
        _ = jwt.decode(
            token,
            signing_key,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=issuer,
            options={"verify_aud": False}
        )

        return signing_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials")

async def validate_auth(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
):
    settings = get_api_settings()

    if settings.VALIDATE_API:
        return await verify_jwt(
            credentials=credentials
        )

    return {"verified": True}

async def verify_jwt(
    *,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    settings = get_api_settings()

    token = credentials.credentials
    public_key = await get_public_key(
        token=token,
    )

    if settings.ENV == 'pro':
        issuer = settings.JWT_ISSUER_HG_APP
    elif settings.ENV == 'dev':
        issuer = settings.JWT_ISSUER_HG_DEV

    try:
        _ = jwt.decode(
            token,
            public_key,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=issuer,
            options={"verify_aud": False}
        )
        return {"verified": True}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials")
