from functools import wraps
from typing import Callable, Dict

from fastapi import APIRouter


class BaseUsecase:
    _methods: Dict[str, Dict] = {}

    @classmethod
    def method(cls, method: str, url: str):
        """
        Decorator to register a method with its HTTP details.
        """

        def decorator(func: Callable):
            if not hasattr(cls, "_methods"):
                cls._methods = {}
            cls._methods[func.__name__] = {"method": method, "url": url, "func": func}

            @wraps(func)
            async def wrapped(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapped

        return decorator

    @classmethod
    def as_direct_client(cls):
        """
        Dynamically create a direct client class.
        """
        methods = cls._methods

        class DirectClient:
            def __init__(self):
                self.usecase = cls()

        # Dynamically generate methods
        for name, details in methods.items():

            async def method(self, _func=details["func"], *args, **kwargs):
                return await _func(self.usecase, *args, **kwargs)

            setattr(DirectClient, name, method)

        return DirectClient

    @classmethod
    def as_api_client(cls, base_url: str):
        """
        Dynamically create an API client class.
        """
        methods = cls._methods

        class ApiClient:
            def __init__(self):
                self.base_url = base_url

        # Dynamically generate methods
        for name, details in methods.items():

            async def method(
                self, _url=details["url"], _method=details["method"], *args, **kwargs
            ):
                import httpx

                async with httpx.AsyncClient() as client:
                    url = self.base_url + _url.format(**kwargs)
                    if _method.lower() == "get":
                        response = await client.get(url)
                    elif _method.lower() == "post":
                        response = await client.post(url, json=kwargs)
                    # Add more HTTP methods as needed
                    response.raise_for_status()
                    return response.json()

            setattr(ApiClient, name, method)

        return ApiClient

    @classmethod
    def serve_route(cls, app: APIRouter):
        """
        Dynamically add routes to FastAPI.
        """
        for name, details in cls._methods.items():
            app.add_api_route(
                path=details["url"],
                endpoint=details["func"],
                methods=[details["method"].upper()],
            )
