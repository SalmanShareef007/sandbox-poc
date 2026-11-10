
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings


bearer_scheme = HTTPBearer()


@lru_cache
def get_jwks_client(tenant_id: str) -> PyJWKClient:
    jwks_url = (
        f"https://login.microsoftonline.com/"
        f"{tenant_id}/discovery/v2.0/keys"
    )
    return PyJWKClient(jwks_url)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:

    tenant_id = settings.ENTRA_TENANT_ID
    audience = settings.ENTRA_API_AUDIENCE

    if not tenant_id or not audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication configuration is incomplete.",
        )

    token = credentials.credentials

    try:
        jwks_client = get_jwks_client(tenant_id)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=(
                f"https://login.microsoftonline.com/"
                f"{tenant_id}/v2.0"
            ),
            options={"require": ["exp", "iss", "aud"]},
        )

        if claims.get("tid") != tenant_id:
            raise InvalidTokenError("Unexpected tenant.")

        if not claims.get("oid"):
            raise InvalidTokenError("Object ID is missing.")

        scopes = str(claims.get("scp", "")).split()
        if settings.ENTRA_REQUIRED_SCOPE not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The required delegated API scope is missing.",
            )

        if settings.ENTRA_ALLOWED_CLIENT_IDS and claims.get("azp") not in settings.ENTRA_ALLOWED_CLIENT_IDS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This client application is not authorized.",
            )

        return claims

    except (InvalidTokenError, PyJWKClientError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def user_email(claims: dict) -> str:
    return (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or ""
    )


def is_admin(claims: dict) -> bool:
    roles = claims.get("roles")
    return isinstance(roles, list) and settings.ADMIN_ROLE in roles


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the sandbox administrator role.",
        )
    return current_user
