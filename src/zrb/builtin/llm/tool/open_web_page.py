import json

import requests
from bs4 import BeautifulSoup

from zrb.builtin.llm.tool._helper import parse_content


def open_web_page(url: str) -> str:
    """Get content from a web page."""
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa
        },
    )
    if response.status_code != 200:
        raise Exception(
            f"Error: Unable to retrieve search results (status code: {response.status_code})"  # noqa
        )
    soup = BeautifulSoup(response.text, "html.parser")
    return json.dumps(parse_content(soup))
