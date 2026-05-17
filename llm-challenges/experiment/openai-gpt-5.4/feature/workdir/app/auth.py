from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


UNAUTHORIZED_ERROR = HTTPException(status_code=401, detail="Invalid or missing API key")


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """
    Validates X-API-Key header against VALID_API_KEYS.
    Returns the username on success.
    """
    if x_api_key is None:
        raise UNAUTHORIZED_ERROR

    username = VALID_API_KEYS.get(x_api_key)
    if username is None:
        raise UNAUTHORIZED_ERROR

    return username
