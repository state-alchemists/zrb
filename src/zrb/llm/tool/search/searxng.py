from typing import Any
import subprocess
import requests

from zrb.config.config import CFG


def _is_docker_installed() -> bool:
    """Check if Docker is installed and accessible."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _is_default_searxng_url(url: str) -> bool:
    """Check if the Searxng URL is the default localhost URL."""
    return url.startswith("http://localhost:") or url.startswith("http://127.0.0.1:")


def search_internet(
    query: str,
    page: int = 1,
    safe_search: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Performs a live internet search using SearXNG, an aggregator that combines results from multiple search engines.

    **WHEN TO USE:**
    - To gather diverse perspectives or information from across the web.
    - To retrieve the latest data, documentation, or public resources.

    **ARGS:**
    - `query`: The search string or question.
    - `page`: Result page number (default 1).
    """
    if safe_search is None:
        safe_search = CFG.SEARXNG_SAFE
    if language is None:
        language = CFG.SEARXNG_LANG

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    try:
        response = requests.get(
            url=f"{CFG.SEARXNG_BASE_URL}/search",
            headers={"User-Agent": user_agent},
            params={
                "q": query,
                "format": "json",
                "pageno": page,
                "safesearch": safe_search,
                "language": language,
            },
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(
                f"Error: Unable to retrieve search results (status code: {response.status_code})"
            )
        return response.json()
    
    except requests.exceptions.ConnectionError as e:
        # Check if this is a connection error to localhost (Searxng not running)
        searxng_url = CFG.SEARXNG_BASE_URL
        is_default_url = _is_default_searxng_url(searxng_url)
        docker_installed = _is_docker_installed()
        
        error_msg = f"Error: Unable to connect to Searxng at {searxng_url}. Connection refused."
        
        # Only provide suggestion if all conditions are met
        if is_default_url and docker_installed:
            root_group = CFG.ROOT_GROUP_NAME
            suggestion = f"[SYSTEM SUGGESTION]: Searxng appears to be not running. You can start it with: {root_group} searxng start"
            error_msg += f"\n\n{suggestion}"
        
        elif is_default_url and not docker_installed:
            suggestion = "[SYSTEM SUGGESTION]: Searxng is not running and Docker is not installed. Please install Docker first to run Searxng locally."
            error_msg += f"\n\n{suggestion}"
        
        raise Exception(error_msg) from e
    
    except requests.exceptions.Timeout as e:
        error_msg = f"Error: Connection to Searxng at {CFG.SEARXNG_BASE_URL} timed out."
        
        # Check conditions for suggestion
        is_default_url = _is_default_searxng_url(CFG.SEARXNG_BASE_URL)
        docker_installed = _is_docker_installed()
        
        if is_default_url and docker_installed:
            root_group = CFG.ROOT_GROUP_NAME
            suggestion = f"[SYSTEM SUGGESTION]: Searxng may not be running. You can start it with: {root_group} searxng start"
            error_msg += f"\n\n{suggestion}"
        
        raise Exception(error_msg) from e
    
    except Exception as e:
        # Re-raise other exceptions without modification
        raise