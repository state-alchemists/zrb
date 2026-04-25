import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests

from zrb.llm.tool.search.brave import search_internet as brave_search
from zrb.llm.tool.search.searxng import search_internet as searxng_search
from zrb.llm.tool.search.serpapi import search_internet as serpapi_search


@patch("requests.get")
def test_brave_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    result = brave_search("query")
    assert result == {"results": []}


@patch("requests.get")
def test_serpapi_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"organic_results": []}
    mock_get.return_value = mock_response

    result = serpapi_search("query")
    assert result == {"organic_results": []}


@patch("requests.get")
def test_searxng_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    result = searxng_search("query")
    assert result == {"results": []}


@patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=False)
@patch("requests.get")
def test_searxng_search_connection_error(mock_get, mock_docker_installed):
    mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

    with pytest.raises(Exception) as excinfo:
        searxng_search("query")
    assert "Unable to connect to Searxng" in str(excinfo.value)


class TestSearxngSearch:
    """Tests for SearXNG search through public API."""

    @patch("requests.get")
    def test_searxng_search_with_params(self, mock_get):
        """Test search with custom safe_search and language."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": ["item"]}
        mock_get.return_value = mock_response

        result = searxng_search("test query", page=2, safe_search=1, language="fr")

        assert result == {"results": ["item"]}
        # Verify params were passed correctly
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["pageno"] == 2
        assert call_kwargs[1]["params"]["safesearch"] == 1
        assert call_kwargs[1]["params"]["language"] == "fr"

    @patch("requests.get")
    def test_searxng_search_non_200_status(self, mock_get):
        """Test search with non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "status code: 500" in str(excinfo.value)

    @patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=True)
    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_searxng_connection_error_with_docker(
        self, mock_get, mock_cfg, mock_docker
    ):
        """Test connection error when Docker is installed."""
        mock_cfg.SEARXNG_BASE_URL = "http://localhost:8080"
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "Unable to connect to Searxng" in str(excinfo.value)
        assert "Searxng appears to be not running" in str(excinfo.value)

    @patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=False)
    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_searxng_connection_error_no_docker(self, mock_get, mock_cfg, mock_docker):
        """Test connection error when Docker is not installed."""
        mock_cfg.SEARXNG_BASE_URL = "http://localhost:8080"
        mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "Unable to connect to Searxng" in str(excinfo.value)
        assert "Docker is not installed" in str(excinfo.value)

    @patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=True)
    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_searxng_timeout_with_docker(self, mock_get, mock_cfg, mock_docker):
        """Test timeout error when Docker is installed."""
        mock_cfg.SEARXNG_BASE_URL = "http://localhost:8080"
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_get.side_effect = requests.exceptions.Timeout("Timed out")

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "timed out" in str(excinfo.value)

    @patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=False)
    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_searxng_timeout_no_docker(self, mock_get, mock_cfg, mock_docker):
        """Test timeout error when Docker is not installed."""
        mock_cfg.SEARXNG_BASE_URL = "http://example.com"  # Non-localhost
        mock_get.side_effect = requests.exceptions.Timeout("Timed out")

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "timed out" in str(excinfo.value)
        # Should not have suggestion since it's not localhost

    @patch("zrb.llm.tool.search.searxng.is_docker_installed", return_value=True)
    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_searxng_remote_url_connection_error(self, mock_get, mock_cfg, mock_docker):
        """Test connection error with remote URL (not localhost)."""
        mock_cfg.SEARXNG_BASE_URL = "https://remote.example.com"
        mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

        with pytest.raises(Exception) as excinfo:
            searxng_search("query")
        assert "Unable to connect to Searxng" in str(excinfo.value)
        # Should not have Docker suggestion for remote URL
        assert "Docker" not in str(excinfo.value)

    @patch("requests.get")
    def test_searxng_generic_exception(self, mock_get):
        """Test generic exception is re-raised."""
        mock_get.side_effect = ValueError("Something went wrong")

        with pytest.raises(ValueError):
            searxng_search("query")


class TestSearxngHelpers:
    """Tests for SearXNG helper functions."""

    def testis_default_searxng_url_localhost(self):
        """Test localhost URL detection."""
        from zrb.llm.tool.search.searxng import is_default_searxng_url

        assert is_default_searxng_url("http://localhost:8080") is True
        assert is_default_searxng_url("http://127.0.0.1:8080") is True

    def testis_default_searxng_url_remote(self):
        """Test remote URL detection."""
        from zrb.llm.tool.search.searxng import is_default_searxng_url

        assert is_default_searxng_url("https://searx.be") is False
        assert is_default_searxng_url("https://example.com") is False

    @patch("subprocess.run")
    def testis_docker_installed_success(self, mock_run):
        """Test is_docker_installed returns True when Docker is available."""
        from zrb.llm.tool.search.searxng import is_docker_installed

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        assert is_docker_installed() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def testis_docker_installed_failure(self, mock_run):
        """Test is_docker_installed returns False when Docker fails."""
        from zrb.llm.tool.search.searxng import is_docker_installed

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        assert is_docker_installed() is False

    @patch("subprocess.run")
    def testis_docker_installed_subprocess_error(self, mock_run):
        """Test is_docker_installed handles subprocess error."""
        from zrb.llm.tool.search.searxng import is_docker_installed

        mock_run.side_effect = subprocess.SubprocessError("Failed")

        assert is_docker_installed() is False

    @patch("subprocess.run")
    def testis_docker_installed_file_not_found(self, mock_run):
        """Test is_docker_installed handles FileNotFoundError."""
        from zrb.llm.tool.search.searxng import is_docker_installed

        mock_run.side_effect = FileNotFoundError("docker not found")

        assert is_docker_installed() is False


class TestBraveSearch:
    """Tests for Brave search through public API."""

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_with_params(self, mock_get, mock_cfg):
        """Test Brave search with parameters."""
        mock_cfg.BRAVE_API_KEY = "test-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        result = brave_search("test", page=2)
        assert result == {"results": []}

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_custom_api_key(self, mock_get, mock_cfg):
        """Test Brave search with custom API key."""
        mock_cfg.BRAVE_API_KEY = "default-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        result = brave_search("test", api_key="custom-key")
        assert result == {"results": []}
        # Verify custom key was used
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["headers"]["x-subscription-token"] == "custom-key"

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_401_error(self, mock_get, mock_cfg):
        """Test Brave search handles 401 authentication error."""
        mock_cfg.BRAVE_API_KEY = "test-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            brave_search("test")
        assert "authentication failed" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_429_error(self, mock_get, mock_cfg):
        """Test Brave search handles 429 rate limit error."""
        mock_cfg.BRAVE_API_KEY = "test-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            brave_search("test")
        assert "rate limit" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_400_error(self, mock_get, mock_cfg):
        """Test Brave search handles 400-series client errors."""
        mock_cfg.BRAVE_API_KEY = "test-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            brave_search("test")
        assert "request failed" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_brave_search_500_error(self, mock_get, mock_cfg):
        """Test Brave search handles 500-series server errors."""
        mock_cfg.BRAVE_API_KEY = "test-key"
        mock_cfg.BRAVE_API_SAFE = "moderate"
        mock_cfg.BRAVE_API_LANG = "en"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            brave_search("test")
        assert "server error" in str(excinfo.value).lower()


class TestSerpapiSearch:
    """Tests for SerpAPI search through public API."""

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_with_params(self, mock_get, mock_cfg):
        """Test SerpAPI search with parameters."""
        mock_cfg.SERPAPI_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic_results": []}
        mock_get.return_value = mock_response

        result = serpapi_search("test", page=2)
        assert result == {"organic_results": []}

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_custom_api_key(self, mock_get, mock_cfg):
        """Test SerpAPI search with custom API key."""
        mock_cfg.SERPAPI_API_KEY = "default-key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic_results": []}
        mock_get.return_value = mock_response

        result = serpapi_search("test", api_key="custom-key")
        assert result == {"organic_results": []}
        # Verify custom key was used
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["api_key"] == "custom-key"

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_401_error(self, mock_get, mock_cfg):
        """Test SerpAPI search handles 401 authentication error."""
        mock_cfg.SERPAPI_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            serpapi_search("test")
        assert "authentication failed" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_429_error(self, mock_get, mock_cfg):
        """Test SerpAPI search handles 429 rate limit error."""
        mock_cfg.SERPAPI_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            serpapi_search("test")
        assert "rate limit" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_400_error(self, mock_get, mock_cfg):
        """Test SerpAPI search handles 400-series client errors."""
        mock_cfg.SERPAPI_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            serpapi_search("test")
        assert "request failed" in str(excinfo.value).lower()

    @patch("zrb.config.config.CFG", autospec=True)
    @patch("requests.get")
    def test_serpapi_search_500_error(self, mock_get, mock_cfg):
        """Test SerpAPI search handles 500-series server errors."""
        mock_cfg.SERPAPI_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as excinfo:
            serpapi_search("test")
        assert "server error" in str(excinfo.value).lower()
