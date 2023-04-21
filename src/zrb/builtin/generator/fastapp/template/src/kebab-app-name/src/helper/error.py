from typing import Any, Dict, Union
from fastapi import HTTPException


def get_api_error_detail(detail):
    return {'api_error': detail}


def create_http_api_exception(
    status_code: int,
    detail: Any = None,
    headers: Union[Dict[str, Any], None] = None
) -> HTTPException:
    response_headers = {} if headers is None else headers
    response_headers['api-error'] = 'yes'
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=response_headers
    )


API_ERROR_MAP = {
    'not found': create_http_api_exception(
        status_code=404, detail='Not Found'
    ),
    'forbidden': create_http_api_exception(
        status_code=403, detail='Forbidden'
    ),
    'unauthorized': create_http_api_exception(
        status_code=403, detail='Unauthorized'
    ),
    'unauthenticated': create_http_api_exception(
        status_code=401, detail='Unauthenticated'
    ),
}

INTERNAL_API_SERVER_ERROR = HTTPException(
    status_code=500, detail='Internal Server Error'
)


def get_http_api_error(error: Exception) -> HTTPException:
    error_str = f'{error}'
    error_list = [
        API_ERROR_MAP[key]
        for key in API_ERROR_MAP if error_str.lower().startswith(key)
    ]
    if len(error_list) > 0:
        return error_list[0]
    return INTERNAL_API_SERVER_ERROR
