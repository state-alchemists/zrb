from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """
    Validates X-API-Key header against VALID_API_KEYS.
    Returns the username on success.
    Raises HTTPException(401) if missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return VALID_API_KEYS[x_api_key]
