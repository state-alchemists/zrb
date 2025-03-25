import json
from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlparse

import requests

# Constants
DEFAULT_TIMEOUT = 10  # seconds
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def validate_url(url: str) -> bool:
    """
    Validate if the URL is properly formatted and uses http or https scheme.
    
    Args:
        url: The URL to validate
        
    Returns:
        bool: True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False


def open_web_page(url: str) -> str:
    """
    Get content from a web page.
    
    Args:
        url: The URL of the webpage to fetch
        
    Returns:
        str: JSON string containing parsed web page content and links
        
    Raises:
        ValueError: If URL is invalid
        ConnectionError: If unable to connect to the URL
        TimeoutError: If request times out
    """
    if not validate_url(url):
        raise ValueError(f"Invalid URL format: {url}")
    
    try:
        response = requests.get(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return json.dumps(parse_html_text(response.text, base_url=url))
    except requests.exceptions.HTTPError as e:
        raise ConnectionError(f"HTTP Error: {e} (status code: {response.status_code})")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Error: Unable to connect to {url}")
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Error: Request to {url} timed out")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error: {str(e)}")


def create_search_internet_tool(serp_api_key: str) -> Callable[[str, int], str]:
    """
    Create a tool function for searching the internet using SerpAPI.
    
    Args:
        serp_api_key: The API key for SerpAPI
        
    Returns:
        A callable function that performs internet searches
    """
    def search_internet(
        query: Annotated[str, "Search query"],
        num_results: Annotated[int, "Search result count, by default 10"] = 10,
    ) -> str:
        """
        Search factual information from the internet using Google.
        
        Args:
            query: The search query
            num_results: Number of results to return (default: 10)
            
        Returns:
            JSON string with search results
            
        Raises:
            ValueError: If query is empty
            ConnectionError: If the search request fails
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")
            
        try:
            response = requests.get(
                "https://serpapi.com/search",
                headers={"User-Agent": DEFAULT_USER_AGENT},
                params={
                    "q": query,
                    "num": num_results,
                    "hl": "en",
                    "safe": "off",
                    "api_key": serp_api_key,
                },
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return json.dumps(parse_html_text(response.text))
        except requests.exceptions.HTTPError as e:
            status = response.status_code
            raise ConnectionError(f"Search API error: {e} (status code: {status})")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Error: Unable to connect to search API")
        except requests.exceptions.Timeout:
            raise TimeoutError("Error: Search request timed out")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error with search request: {str(e)}")

    return search_internet


def search_wikipedia(query: Annotated[str, "Search query"]) -> str:
    """
    Search for information on Wikipedia.
    
    Args:
        query: The search query
        
    Returns:
        JSON string with Wikipedia search results
        
    Raises:
        ValueError: If query is empty
        ConnectionError: If the request fails
    """
    if not query.strip():
        raise ValueError("Wikipedia search query cannot be empty")
        
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json"
        }
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Wikipedia API error: {str(e)}")


def search_arxiv(
    query: Annotated[str, "Search query"],
    num_results: Annotated[int, "Search result count, by default 10"] = 10,
) -> str:
    """
    Search for research papers on arXiv.
    
    Args:
        query: The search query
        num_results: Number of results to return (default: 10)
        
    Returns:
        XML response from arXiv API converted to string
        
    Raises:
        ValueError: If query is empty
        ConnectionError: If the request fails
    """
    if not query.strip():
        raise ValueError("arXiv search query cannot be empty")
        
    try:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(num_results, 50)  # Limit max results to 50
        }
        response = requests.get(
            "http://export.arxiv.org/api/query",
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        # Converting bytes to string for consistent return type
        return response.content.decode('utf-8')
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"arXiv API error: {str(e)}")


def parse_html_text(html_text: str, base_url: str = "") -> dict:
    """
    Parse HTML content to extract text and links.
    
    Args:
        html_text: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        Dictionary containing extracted text content and links
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    ignored_tags = [
        "script", "link", "meta", "style", "code",
        "footer", "nav", "header", "aside"
    ]
    
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        links = []
        
        # Extract links and convert relative URLs to absolute if base_url provided
        for anchor in soup.find_all("a"):
            if not anchor or "href" not in anchor.attrs:
                continue
                
            link: str = anchor["href"]
            
            # Handle relative URLs if base_url is provided
            if base_url and (link.startswith("/") or link.startswith("#")):
                link = urljoin(base_url, link)
                
            # Skip empty links and javascript
            if not link or link.startswith("javascript:"):
                continue
                
            links.append(link)
            
        # Remove unwanted tags
        for tag in soup(ignored_tags):
            tag.decompose()
            
        # Extract text with proper spacing
        clean_text = soup.get_text(separator=" ", strip=True)
        
        return {
            "content": clean_text,
            "links_on_page": links
        }
    except Exception as e:
        # Return error information if parsing fails
        return {
            "content": f"Error parsing HTML: {str(e)}",
            "links_on_page": []
        }
