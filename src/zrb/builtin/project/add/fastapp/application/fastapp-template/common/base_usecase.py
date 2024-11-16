from enum import Enum
from functools import wraps
from typing import Any, Callable, Sequence

from fastapi import APIRouter, params
from fastapi.routing import APIRoute
from fastapi.types import IncEx
from fastapi.utils import generate_unique_id
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute


class RouteParam(BaseModel):
    path: str
    response_model: Any
    status_code: int | None
    tags: list[str | Enum] | None
    dependencies: Sequence[params.Depends] | None
    summary: str | None
    description: str
    response_description: str
    responses: dict[int | str, dict[str, Any]] | None
    deprecated: bool | None
    methods: set[str] | list[str] | None
    operation_id: str | None
    response_model_include: IncEx | None
    response_model_exclude: IncEx | None
    response_model_by_alias: bool
    response_model_exclude_unset: bool
    response_model_exclude_defaults: bool
    response_model_exclude_none: bool
    include_in_schema: bool
    response_class: type[Response]
    name: str | None
    callbacks: list[BaseRoute] | None
    openapi_extra: dict[str, Any] | None
    generate_unique_id_function: Callable[[APIRoute], str]
    func: Callable


class BaseUsecase:
    _methods: dict[str, RouteParam] = {}

    @classmethod
    def route(
        cls,
        path: str,
        *,
        response_model: Any = None,
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        dependencies: Sequence[params.Depends] | None = None,
        summary: str | None = None,
        description: str = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        methods: set[str] | list[str] | None = None,
        operation_id: str | None = None,
        response_model_include: IncEx | None = None,
        response_model_exclude: IncEx | None = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        response_class: type[Response] = JSONResponse,
        name: str | None = None,
        callbacks: list[BaseRoute] | None = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[APIRoute], str] = generate_unique_id,
    ):
        """
        Decorator to register a method with its HTTP details.
        """

        def decorator(func: Callable):
            if not hasattr(cls, "_methods"):
                cls._methods = {}
            cls._methods[func.__name__] = RouteParam(
                path=path,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                dependencies=dependencies,
                summary=summary,
                description=description,
                response_description=response_description,
                responses=responses,
                deprecated=deprecated,
                methods=methods,
                operation_id=operation_id,
                response_model_include=response_model_include,
                response_model_exclude=response_model_exclude,
                response_model_by_alias=response_model_by_alias,
                response_model_exclude_unset=response_model_exclude_unset,
                response_model_exclude_defaults=response_model_exclude_defaults,
                response_model_exclude_none=response_model_exclude_none,
                include_in_schema=include_in_schema,
                response_class=response_class,
                name=name,
                callbacks=callbacks,
                openapi_extra=openapi_extra,
                generate_unique_id_function=generate_unique_id_function,
                func=func,
            )

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
        for name, route_param in cls._methods.items():
            app.add_api_route(
                path=route_param.path,
                response_model=route_param.response_model,
                status_code=route_param.status_code,
                tags=route_param.tags,
                dependencies=route_param.dependencies,
                summary=route_param.summary,
                description=route_param.description,
                response_description=route_param.response_description,
                responses=route_param.responses,
                deprecated=route_param.deprecated,
                methods=route_param.methods,
                operation_id=route_param.operation_id,
                response_model_include=route_param.response_model_include,
                response_model_exclude=route_param.response_model_exclude,
                response_model_by_alias=route_param.response_model_by_alias,
                response_model_exclude_unset=route_param.response_model_exclude_unset,
                response_model_exclude_defaults=route_param.response_model_exclude_defaults,
                response_model_exclude_none=route_param.response_model_exclude_none,
                include_in_schema=route_param.include_in_schema,
                response_class=route_param.response_class,
                name=route_param.name,
                callbacks=route_param.callbacks,
                openapi_extra=route_param.openapi_extra,
                generate_unique_id_function=route_param.generate_unique_id_function,
                endpoint=route_param.func,
            )
