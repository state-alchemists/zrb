from typing import Any, Mapping, Optional

from fastapi import HTTPException


class HTTPAPIException(HTTPException):
    def __init__(
        self,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        headers: Optional[Mapping[str, Any]] = None,
        error: Optional[Exception] = None,
    ):
        if error is HTTPException:
            status_code = (error.status_code,)
            detail = (error.detail,)
            headers = self._get_headers(error.headers)
            return super().__init__(
                status_code=status_code, detail=detail, headers=headers
            )
        if error is not None:
            error_message = f"{error}"
        status_code = self._get_status_code(status_code, error_message)
        headers = self._get_headers(headers)
        return super().__init__(
            status_code=status_code, detail=error_message, headers=headers
        )

    def _get_status_code(
        self, status_code: Optional[int], error_message: Optional[str]
    ) -> int:
        if status_code is not None:
            return status_code
        if error_message is None:
            return 500
        if error_message.lower().startswith("not found"):
            return 404
        if error_message.lower().startswith("forbidden"):
            return 403
        if error_message.lower().startswith("unauthorized"):
            return 403
        if error_message.lower().startswith("unauthenticated"):
            return 401
        if error_message.lower().startswith("unprocessable"):
            return 422
        if error_message.lower().startswith("invalid"):
            return 422
        return 500

    def _get_headers(
        self, original_headers: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        headers = {} if original_headers is None else dict(original_headers)
        headers["api-error"] = "yes"
        return headers
