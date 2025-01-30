import inspect
from enum import Enum
from functools import partial
from logging import Logger
from typing import Any, Callable, Union, get_args, get_origin

import httpx
from fastapi import APIRouter, Depends
from my_app_name.common.error import ClientAPIError
from pydantic import BaseModel


class RouteParam:
    def __init__(
        self,
        path: str,
        response_model: Any,
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str = "",
        deprecated: bool | None = None,
        methods: set[str] | list[str] | None = None,
        func: Callable | None = None,
    ):
        self.path = path
        self.response_model = response_model
        self.status_code = status_code
        self.tags = tags
        self.summary = summary
        self.description = description
        self.deprecated = deprecated
        self.methods = methods
        self.func = func


class BaseService:
    _route_params: dict[str, RouteParam] = {}

    def __init__(self, logger: Logger):
        self._logger = logger
        self._route_params: dict[str, RouteParam] = {}
        for name, method in self.__class__.__dict__.items():
            if hasattr(method, "__route_param__"):
                self._route_params[name] = getattr(method, "__route_param__")

    @property
    def logger(self) -> Logger:
        return self._logger

    @classmethod
    def route(
        cls,
        path: str,
        *,
        response_model: Any = None,
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str = None,
        deprecated: bool | None = None,
        methods: set[str] | list[str] | None = None,
    ):
        """
        Decorator to register a method with its HTTP details.
        """

        def decorator(func: Callable):
            # Check for Depends in function parameters
            sig = inspect.signature(func)
            for param in sig.parameters.values():
                if param.annotation is Depends or (
                    hasattr(param.annotation, "__origin__")
                    and param.annotation.__origin__ is Depends
                ):
                    raise ValueError(
                        f"Depends is not allowed in function parameters. Found in {func.__name__}"  # noqa
                    )
            # Inject __route_param__ property to the method
            # Method with __route_param__ property will automatically
            # registered to self._route_param and will be automatically exposed
            # into DirectClient and APIClient
            func.__route_param__ = RouteParam(
                path=path,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                summary=summary,
                description=description,
                deprecated=deprecated,
                methods=methods,
                func=func,
            )
            return func

        return decorator

    def as_direct_client(self):
        """
        Dynamically create a direct client class.
        """
        _methods = self._route_params
        DirectClient = _create_client_class("DirectClient")
        for name, details in _methods.items():
            func = details.func
            client_method = _create_direct_client_method(self._logger, func, self)
            # Use __get__ to make a bounded method,
            # ensuring that client_method use DirectClient as `self`
            setattr(DirectClient, name, client_method.__get__(DirectClient))
        return DirectClient

    def as_api_client(self, base_url: str):
        """
        Dynamically create an API client class.
        """
        _methods = self._route_params
        APIClient = _create_client_class("APIClient")
        # Dynamically generate methods
        for name, param in _methods.items():
            client_method = _create_api_client_method(self._logger, param, base_url)
            # Use __get__ to make a bounded method,
            # ensuring that client_method use APIClient as `self`
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
                summary=route_param.summary,
                description=route_param.description,
                deprecated=route_param.deprecated,
                methods=route_param.methods,
            )


def _create_client_class(name):
    class Client:
        pass

    Client.__name__ = name
    return Client


def _create_direct_client_method(logger: Logger, func: Callable, service: BaseService):
    async def client_method(self, *args, **kwargs):
        return await func(service, *args, **kwargs)

    return client_method


def _create_api_client_method(logger: Logger, route_param: RouteParam, base_url: str):
    async def client_method(*args, **kwargs):
        url = base_url + route_param.path
        method = _get_api_client_method(route_param)
        body_param_names = _get_api_client_body_param_names(route_param, method)
        path_params, query_params, body_params = _create_api_client_request_params(
            route_param, body_param_names, args, kwargs
        )
        # Format the URL with path parameters
        url = url.format(**path_params)
        json_body_params = None if method == "get" else body_params
        logger.info(
            f"Sending request to {url} with method {method}, json={json_body_params}, params={query_params}"  # noqa
        )
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method, url=url, params=query_params, json=json_body_params
            )
            logger.info(
                f"Received response: status={response.status_code}, content={response.content}"
            )
            if response.status_code >= 400:
                error_detail = (
                    response.json()
                    if response.headers.get("content-type") == "application/json"
                    else response.text
                )
                raise ClientAPIError(response.status_code, error_detail)
            return _parse_api_client_response(logger, route_param, response)

    return client_method


def _parse_api_client_response(
    logger: Logger, route_param: RouteParam, response: Any
) -> Any:
    sig = inspect.signature(route_param.func)
    try:
        response_data = response.json()
    except Exception:
        logger.warning("Failed to parse JSON")
        return None
    return_annotation = sig.return_annotation  # e.g., list[User]
    if return_annotation is inspect.Signature.empty:
        logger.warning("No return annotation detected, return value as is")
        return response_data  # No return type specified, return raw JSON
    origin = get_origin(return_annotation)  # e.g., list
    args = get_args(return_annotation)  # e.g., (User,)
    try:
        if origin is None:  # Not a generic type, so check it directly
            if inspect.isclass(return_annotation) and issubclass(
                return_annotation, BaseModel
            ):
                if response_data:
                    return return_annotation.model_validate(response_data)
                return None
        elif origin in {list, set, tuple} and args:
            model_type = args[0]
            if inspect.isclass(model_type) and issubclass(model_type, BaseModel):
                if isinstance(response_data, list):
                    return [model_type.model_validate(item) for item in response_data]
                elif isinstance(response_data, tuple):
                    return tuple(
                        model_type.model_validate(item) for item in response_data
                    )
                elif isinstance(response_data, set):
                    return {model_type.model_validate(item) for item in response_data}
                return None
        elif origin is Union and len(args) == 2 and type(None) in args:
            model_type = next(
                (
                    arg
                    for arg in args
                    if inspect.isclass(arg) and issubclass(arg, BaseModel)
                ),
                None,
            )
            if response_data and model_type:
                return model_type.model_validate(response_data)
            return None
        elif origin is dict and len(args) == 2:
            key_type, value_type = args
            if inspect.isclass(value_type) and issubclass(value_type, BaseModel):
                if inspect(response_data, dict):
                    return {
                        k: value_type.model_validate(v)
                        for k, v in response_data.items()
                    }
                return None
        return response_data
    except Exception:
        logger.warning(
            "Return annotation detected, but parsing error, return value as is"
        )
        return response_data


def _create_api_client_request_params(
    route_param: RouteParam,
    body_param_names: list[str],
    args: list[Any],
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    # Get the signature of the original function
    sig = inspect.signature(route_param.func)
    # Bind the arguments to the signature
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    # Prepare the request
    path_params = {}
    query_params = {}
    body_params = {}
    for name, value in bound_args.arguments.items():
        if name == "self":
            continue
        if f"{{{name}}}" in route_param.path:
            path_params[name] = value
        elif name not in body_param_names:
            query_params[name] = _parse_api_client_param(value)
        elif len(body_param_names) == 1 and name == body_param_names[0]:
            # If there's only one body parameter, use its value directly
            body_params = _parse_api_client_param(value)
        else:
            body_params[name] = _parse_api_client_param(value)
    return path_params, query_params, body_params


def _parse_api_client_param(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump()
    elif isinstance(data, dict):
        return {key: _parse_api_client_param(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_parse_api_client_param(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(_parse_api_client_param(item) for item in data)
    elif isinstance(data, set):
        return {_parse_api_client_param(item) for item in data}
    else:
        return data


def _get_api_client_method(route_param: RouteParam) -> str:
    if isinstance(route_param.methods, list):
        return route_param.methods[0].lower()
    return route_param.methods.lower()


def _get_api_client_body_param_names(route_param: RouteParam, method: str):
    sig = inspect.signature(route_param.func)
    function_params = list(sig.parameters.values())
    return [
        p.name
        for p in function_params
        if (
            p.name != "self"
            and f"{{{p.name}}}" not in route_param.path
            and p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            and (
                method not in ["get", "delete"]
                or (method == "delete" and p.annotation not in [str, float, bool])
            )
        )
    ]
