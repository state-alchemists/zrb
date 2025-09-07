import json
from collections.abc import Callable
from urllib.parse import urljoin

_DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa


async def open_web_page(url: str) -> str:
    """
    Fetches, parses, and converts the content of a web page to Markdown.

    This tool "reads" a web page by fetching its content, stripping away
    non-essential elements like scripts and styles, and then converting the
    cleaned HTML into Markdown format. This preserves the semantic structure
    of the content (headings, lists, etc.) while removing clutter. It also
    extracts all hyperlinks and resolves them to absolute URLs.

    Args:
        url (str): The full URL of the web page to open (e.g.,
            "https://example.com/article").

    Returns:
        str: A JSON string containing the page's content in Markdown format
            and a list of all absolute links found on the page.
    """
    html_content, links = await _fetch_page_content(url)
    markdown_content = _convert_html_to_markdown(html_content)
    return json.dumps({"content": markdown_content, "links_on_page": links})


def create_search_internet_tool(serp_api_key: str) -> Callable[[str, int], str]:
    """
    Creates a tool that searches the internet using the SerpAPI Google Search
    API.

    This factory returns a function that can be used to find information on the
    web. The generated tool is the primary way to answer general knowledge
    questions or to find information on topics you are unfamiliar with.

    Args:
        serp_api_key (str): The API key for SerpAPI.

    Returns:
        Callable: A function that takes a search query and returns a list of
            search results.
    """

    def search_internet(query: str, num_results: int = 10) -> str:
        """
        Performs an internet search using Google and returns a summary of the results.

        Use this tool to find information on the web, answer general knowledge questions,
        or research topics.

        Args:
            query (str): The search query.
            num_results (int, optional): The desired number of search results. Defaults to 10.

        Returns:
            str: A formatted string summarizing the search results,
                including titles, links, and snippets.
        """
        import requests

        response = requests.get(
            "https://serpapi.com/search",
            headers={"User-Agent": _DEFAULT_USER_AGENT},
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
        return response.json()

    return search_internet


def search_wikipedia(query: str) -> str:
    """
    Searches for articles on Wikipedia.

    This is a specialized search tool for querying Wikipedia. It's best for
    when the user is asking for definitions, historical information, or
    biographical details that are likely to be found on an encyclopedia.

    Args:
        query (str): The search term or question.

    Returns:
        str: The raw JSON response from the Wikipedia API, containing a list of
            search results.
    """
    import requests

    params = {"action": "query", "list": "search", "srsearch": query, "format": "json"}
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        headers={"User-Agent": _DEFAULT_USER_AGENT},
        params=params,
    )
    return response.json()


def search_arxiv(query: str, num_results: int = 10) -> str:
    """
    Searches for academic papers and preprints on ArXiv.

    Use this tool when the user's query is scientific or technical in nature
    and they are likely looking for research papers, articles, or academic
    publications.

    Args:
        query (str): The search query, which can include keywords, author
            names, or titles.
        num_results (int, optional): The maximum number of results to return.
            Defaults to 10.

    Returns:
        str: The raw XML response from the ArXiv API, containing a list of
            matching papers.
    """
    import requests

    params = {"search_query": f"all:{query}", "start": 0, "max_results": num_results}
    response = requests.get(
        "http://export.arxiv.org/api/query",
        headers={"User-Agent": _DEFAULT_USER_AGENT},
        params=params,
    )
    return response.content


async def _fetch_page_content(url: str) -> tuple[str, list[str]]:
    """Fetches the HTML content and all absolute links from a URL."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": _DEFAULT_USER_AGENT})
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
                content = await page.content()
                links = await page.eval_on_selector_all(
                    "a[href]",
                    """
                    (elements, baseUrl) => elements.map(el => {
                        const href = el.getAttribute('href');
                        if (!href || href.startsWith('#')) return null;
                        try {
                            return new URL(href, baseUrl).href;
                        } catch (e) {
                            return null;
                        }
                    }).filter(href => href !== null)
                    """,
                    url,
                )
                return content, links
                # return json.dumps({"content": content, "links": links})
            finally:
                await browser.close()
    except Exception:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
        if response.status_code != 200:
            raise Exception(
                f"Unable to retrieve page content. Status code: {response.status_code}"
            )
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        links = [
            urljoin(url, a["href"])
            for a in soup.find_all("a", href=True)
            if not a["href"].startswith("#")
        ]
        return content, links
        # return json.dumps({"content": content, "links": links})


def _convert_html_to_markdown(html_text: str) -> str:
    """Converts HTML content to a clean Markdown representation."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

    soup = BeautifulSoup(html_text, "html.parser")
    # Remove non-content tags
    for tag in soup(
        ["script", "link", "meta", "style", "header", "footer", "nav", "aside"]
    ):
        tag.decompose()
    # Convert the cleaned HTML to Markdown
    return md(str(soup))
