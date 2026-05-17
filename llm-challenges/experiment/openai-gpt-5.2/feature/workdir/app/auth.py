from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Validate the X-API-Key header and return the associated username."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    username = VALID_API_KEYS.get(x_api_key)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return username
