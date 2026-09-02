"""Shared HTTP-status error formatting for internet-search backends."""

from typing import NoReturn

import requests


class SearchToolError(RuntimeError):
    """A search backend failed in a way the agent should report and route
    around — a failed operation (bad credentials, rate limit, transient
    network failure), not a bad argument, hence `RuntimeError` as the base."""


def raise_http_error(
    response: requests.Response,
    service_name: str,
    docs_url: str,
    key_label: str,
) -> NoReturn:
    """Raise a `[SYSTEM SUGGESTION]`-annotated error for a non-200 search response.

    `service_name` names the backend in prose (e.g. "Brave Search"); `key_label`
    names its API key in prose (e.g. "Brave API key" — backends phrase this
    differently, so it isn't derived from `service_name`); `docs_url` is where
    the user can get/verify a key.
    """
    error_body = response.text[:500] if response.text else "No error details provided"
    status_code = response.status_code
    if status_code == 401:
        raise SearchToolError(
            f"Error: {service_name} authentication failed (status code: {status_code}). "
            f"Response: {error_body}. "
            f"[SYSTEM SUGGESTION]: The API key is invalid or expired. Ask the user to "
            f"verify their {key_label} at {docs_url} and provide a valid one via the "
            f"'api_key' parameter."
        )
    elif status_code == 429:
        raise SearchToolError(
            f"Error: {service_name} rate limit exceeded (status code: {status_code}). "
            f"Response: {error_body}. "
            f"[SYSTEM SUGGESTION]: You have exceeded your {service_name} plan limits. "
            f"Wait before retrying, or ask the user to upgrade their plan."
        )
    elif 400 <= status_code < 500:
        raise SearchToolError(
            f"Error: {service_name} request failed (status code: {status_code}). "
            f"Response: {error_body}. "
            f"[SYSTEM SUGGESTION]: Check your search parameters. The 'language', "
            f"'safe_search', or 'query' may be invalid. Try simplifying the query or "
            f"using default parameters."
        )
    else:
        raise SearchToolError(
            f"Error: {service_name} server error (status code: {status_code}). "
            f"Response: {error_body}. "
            f"[SYSTEM SUGGESTION]: This is likely a temporary {service_name} server "
            f"issue. Retry the search, or inform the user and try again later."
        )
