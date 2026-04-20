from fastapi import Header, HTTPException
from typing import Optional
from .database import VALID_API_KEYS


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Validate ``X-API-Key`` header and return associated username.

    - If the header is missing → 401 "Missing X-API-Key header".
    - If the key is unknown → 401 "Invalid API key".
    - On success returns the username mapped from ``VALID_API_KEYS``.
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    try:
        username = VALID_API_KEYS[x_api_key]
    except KeyError:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return username
