import json
from collections.abc import Callable


async def open_web_page(url: str) -> str:
    """
    Fetches and parses the textual content of a given web page URL.

    Use this tool to "read" a web page. It strips away HTML tags, scripts, and other non-textual elements to provide the clean text content. It also extracts any hyperlinks found on the page. This is useful when you need to understand the content of a specific URL that you have discovered through a search or from another source.

    Args:
        url (str): The full URL of the web page to open (e.g., "https://example.com/article").

    Returns:
        str: A JSON object containing the cleaned text `content` of the page and a list of `links_on_page`.
    """

    async def get_page_content(page_url: str):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
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
        except BaseException:
            import requests

            response = requests.get(url, headers={"User-Agent": user_agent})
            if response.status_code != 200:
                msg = f"Unable to retrieve search results. Status code: {response.status_code}"
                raise Exception(msg)
            return {"content": response.text, "links_on_page": []}

    result = await get_page_content(url)
    # Parse the HTML content
    return json.dumps(parse_html_text(result["content"]))


def create_search_internet_tool(serp_api_key: str) -> Callable[[str, int], str]:
    """
    Creates a tool that searches the internet using the SerpAPI Google Search API.

    This factory returns a function that can be used to find information on the web. The generated tool is the primary way to answer general knowledge questions or to find information on topics you are unfamiliar with.

    Args:
        serp_api_key (str): The API key for SerpAPI.

    Returns:
        Callable: A function that takes a search query and returns a list of search results.
    """

    def search_internet(query: str, num_results: int = 10) -> str:
        """
        Performs an internet search using Google and returns a summary of the results.

        Use this tool to find information on the web, answer general knowledge questions, or research topics.

        Args:
            query (str): The search query.
            num_results (int, optional): The desired number of search results. Defaults to 10.

        Returns:
            str: A JSON object containing the parsed text content from the search results page.
        """
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


def search_wikipedia(query: str) -> str:
    """
    Searches for articles on Wikipedia.

    This is a specialized search tool for querying Wikipedia. It's best for when the user is asking for definitions, historical information, or biographical details that are likely to be found on an encyclopedia.

    Args:
        query (str): The search term or question.

    Returns:
        str: The raw JSON response from the Wikipedia API, containing a list of search results.
    """
    import requests

    params = {"action": "query", "list": "search", "srsearch": query, "format": "json"}
    response = requests.get("https://en.wikipedia.org/w/api.php", params=params)
    return response.json()


def search_arxiv(query: str, num_results: int = 10) -> str:
    """
    Searches for academic papers and preprints on ArXiv.

    Use this tool when the user's query is scientific or technical in nature and they are likely looking for research papers, articles, or academic publications.

    Args:
        query (str): The search query, which can include keywords, author names, or titles.
        num_results (int, optional): The maximum number of results to return. Defaults to 10.

    Returns:
        str: The raw XML response from the ArXiv API, containing a list of matching papers.
    """
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
