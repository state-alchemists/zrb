import json
from collections.abc import Callable
from typing import Annotated


def open_web_page(url: str) -> str:
    """Get content from a web page using a headless browser."""
    import asyncio

    from playwright.async_api import async_playwright

    async def get_page_content(page_url: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Set user agent to mimic a regular browser
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            user_agent += "AppleWebKit/537.36 (KHTML, like Gecko) "
            user_agent += "Chrome/91.0.4472.124 Safari/537.36"
            await page.set_extra_http_headers({"User-Agent": user_agent})
            try:
                # Navigate to the URL with a timeout of 30 seconds
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                # Wait for the content to load
                await page.wait_for_load_state("domcontentloaded")
                # Get the page content
                content = await page.content()
                # Extract all links from the page
                links = await page.eval_on_selector_all(
                    "a[href]",
                    """
                    (elements) => elements.map(el => {
                        const href = el.getAttribute('href');
                        if (href && !href.startsWith('#') && !href.startsWith('/')) {
                            return href;
                        }
                        return null;
                    }).filter(href => href !== null)
                """,
                )
                return {"content": content, "links_on_page": links}
            finally:
                await browser.close()

    # Run the async function in the event loop
    result = asyncio.run(get_page_content(url))
    # Parse the HTML content
    return json.dumps(parse_html_text(result["content"]))


def create_search_internet_tool(serp_api_key: str) -> Callable[[str, int], str]:
    def search_internet(
        query: Annotated[str, "Search query"],
        num_results: Annotated[int, "Search result count, by default 10"] = 10,
    ) -> str:
        """Search factual information from the internet by using Google."""
        import requests

        response = requests.get(
            "https://serpapi.com/search",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa
            },
            params={
                "q": query,
                "num": num_results,
                "hl": "en",
                "safe": "off",
                "api_key": serp_api_key,
            },
        )
        if response.status_code != 200:
            raise Exception(
                f"Error: Unable to retrieve search results (status code: {response.status_code})"  # noqa
            )
        return json.dumps(parse_html_text(response.text))

    return search_internet


def search_wikipedia(query: Annotated[str, "Search query"]) -> str:
    """Search on wikipedia"""
    import requests

    params = {"action": "query", "list": "search", "srsearch": query, "format": "json"}
    response = requests.get("https://en.wikipedia.org/w/api.php", params=params)
    return response.json()


def search_arxiv(
    query: Annotated[str, "Search query"],
    num_results: Annotated[int, "Search result count, by default 10"] = 10,
) -> str:
    """Search on Arxiv"""
    import requests

    params = {"search_query": f"all:{query}", "start": 0, "max_results": num_results}
    response = requests.get("http://export.arxiv.org/api/query", params=params)
    return response.content


def parse_html_text(html_text: str) -> dict[str, str]:
    from bs4 import BeautifulSoup

    ignored_tags = [
        "script",
        "link",
        "meta",
        "style",
        "code",
        "footer",
        "nav",
        "header",
        "aside",
    ]
    soup = BeautifulSoup(html_text, "html.parser")
    links = []
    for anchor in soup.find_all("a"):
        if not anchor or "href" not in anchor.attrs:
            continue
        link: str = anchor["href"]
        if link.startswith("#") or link.startswith("/"):
            continue
        links.append(link)
    for tag in soup(ignored_tags):
        tag.decompose()
    html_text = soup.get_text(separator=" ", strip=True)
    return {"content": html_text, "links_on_page": links}
