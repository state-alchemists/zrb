from typing import Any
from abc import ABC, abstractmethod


class AnyRequestHandler(ABC):
    @abstractmethod
    def send_json_response(self, data: Any, http_status: int = 200):
        pass

    @abstractmethod
    def send_html_response(self, html: str, http_status: int = 200):
        pass

    @abstractmethod
    def read_json_request(self) -> Any:
        pass

    @abstractmethod
    def send_css_response(self, css_path: str):
        pass

    @abstractmethod
    def send_image_response(self, image_path: str):
        pass
