from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Validate X-API-Key header against VALID_API_KEYS.

    Returns the associated username on success.
    Raises HTTP 401 if the header is missing or invalid.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    username = VALID_API_KEYS.get(x_api_key)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return username
