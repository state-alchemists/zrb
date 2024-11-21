from enum import Enum
from functools import partial, wraps
from typing import Any, Callable, Sequence

import httpx
from fastapi import APIRouter, params
from fastapi.routing import APIRoute
from fastapi.types import IncEx
from fastapi.utils import generate_unique_id
from starlette.responses import JSONResponse, Response


class RouteParam:
    def __init__(
        self,
        path: str,
        response_model: Any,
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        dependencies: Sequence[params.Depends] | None = None,
        summary: str | None = None,
        description: str = "",
        response_description: str = "",
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
        response_class: type[Response] = Response,
        name: str | None = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[APIRoute], str] | None = None,
        func: Callable | None = None,
    ):
        self.path = path
        self.response_model = response_model
        self.status_code = status_code
        self.tags = tags
        self.dependencies = dependencies
        self.summary = summary
        self.description = description
        self.response_description = response_description
        self.responses = responses
        self.deprecated = deprecated
        self.methods = methods
        self.operation_id = operation_id
        self.response_model_include = response_model_include
        self.response_model_exclude = response_model_exclude
        self.response_model_by_alias = response_model_by_alias
        self.response_model_exclude_unset = response_model_exclude_unset
        self.response_model_exclude_defaults = response_model_exclude_defaults
        self.response_model_exclude_none = response_model_exclude_none
        self.include_in_schema = include_in_schema
        self.response_class = response_class
        self.name = name
        self.openapi_extra = openapi_extra
        self.generate_unique_id_function = generate_unique_id_function
        self.func = func


class BaseUsecase:
    _route_params: dict[str, RouteParam] = {}

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
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[APIRoute], str] = generate_unique_id,
    ):
        """
        Decorator to register a method with its HTTP details.
        """

        def decorator(func: Callable):
            cls._route_params[func.__name__] = RouteParam(
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
                openapi_extra=openapi_extra,
                generate_unique_id_function=generate_unique_id_function,
                func=func,
            )

            @wraps(func)
            async def wrapped(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapped

        return decorator

    def as_direct_client(self):
        """
        Dynamically create a direct client class.
        """
        _methods = self._route_params
        DirectClient = create_client_class("DirectClient")
        for name, details in _methods.items():
            func = details.func
            client_method = create_direct_client_method(func, self)
            setattr(DirectClient, name, client_method.__get__(DirectClient))
        return DirectClient

    def as_api_client(self, base_url: str):
        """
        Dynamically create an API client class.
        """
        _methods = self._route_params
        APIClient = create_client_class("APIClient")
        # Dynamically generate methods
        for name, param in _methods.items():
            client_method = create_api_client_method(param, base_url)
            setattr(APIClient, name, client_method.__get__(APIClient))
        return APIClient

    def serve_route(self, app: APIRouter):
        """
        Dynamically add routes to FastAPI.
        """
        for _, route_param in self._route_params.items():
            bound_func = partial(route_param.func, self)
            bound_func.__name__ = route_param.func.__name__
            bound_func.__doc__ = route_param.func.__doc__
            app.add_api_route(
                path=route_param.path,
                endpoint=bound_func,
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
                openapi_extra=route_param.openapi_extra,
                generate_unique_id_function=route_param.generate_unique_id_function,
            )


def create_client_class(name):
    class Client:
        pass

    Client.__name__ = name
    return Client


def create_direct_client_method(func: Callable, usecase: BaseUsecase):
    async def client_method(self, *args, **kwargs):
        return await func(usecase, *args, **kwargs)

    return client_method


def create_api_client_method(param: RouteParam, base_url: str):
    _url = param.path
    _methods = [method.lower() for method in param.methods]

    async def client_method(self, *args, **kwargs):
        async with httpx.AsyncClient() as client:
            url = base_url + _url.format(**kwargs)
            if "post" in _methods:
                response = await client.post(url, json=kwargs)
            elif "put" in _methods:
                response = await client.put(url, json=kwargs)
            elif "delete" in _methods:
                response = await client.delete(url, json=kwargs)
            else:
                response = await client.get(url, params=kwargs)
            # Add more HTTP methods as needed
            response.raise_for_status()
            return response.json()

    return client_method
