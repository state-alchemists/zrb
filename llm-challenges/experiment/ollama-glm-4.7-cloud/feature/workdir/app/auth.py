from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """
    Validates X-API-Key header against VALID_API_KEYS.
    Returns the username on success.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header is missing")
    
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return VALID_API_KEYS[x_api_key]
