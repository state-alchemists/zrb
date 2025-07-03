import json
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from openai import APIError


# Define a structured error model for tool execution failures
class ToolExecutionError(BaseModel):
    tool_name: str
    error_type: str
    message: str
    details: Optional[str] = None


def extract_api_error_details(error: "APIError") -> str:
    """Extract detailed error information from an APIError."""
    details = f"{error.message}"
    # Try to parse the error body as JSON
    if error.body:
        try:
            if isinstance(error.body, str):
                body_json = json.loads(error.body)
            elif isinstance(error.body, bytes):
                body_json = json.loads(error.body.decode("utf-8"))
            else:
                body_json = error.body
            # Extract error details from the JSON structure
            if isinstance(body_json, dict):
                if "error" in body_json:
                    error_obj = body_json["error"]
                    if isinstance(error_obj, dict):
                        if "message" in error_obj:
                            details += f"\nProvider message: {error_obj['message']}"
                        if "code" in error_obj:
                            details += f"\nError code: {error_obj['code']}"
                        if "status" in error_obj:
                            details += f"\nStatus: {error_obj['status']}"
                # Check for metadata that might contain provider-specific information
                if "metadata" in body_json and isinstance(body_json["metadata"], dict):
                    metadata = body_json["metadata"]
                    if "provider_name" in metadata:
                        details += f"\nProvider: {metadata['provider_name']}"
                    if "raw" in metadata:
                        try:
                            raw_json = json.loads(metadata["raw"])
                            if "error" in raw_json and isinstance(
                                raw_json["error"], dict
                            ):
                                raw_error = raw_json["error"]
                                if "message" in raw_error:
                                    details += (
                                        f"\nRaw error message: {raw_error['message']}"
                                    )
                        except (KeyError, TypeError, ValueError):
                            # If we can't parse the raw JSON, just include it as is
                            details += f"\nRaw error data: {metadata['raw']}"
        except json.JSONDecodeError:
            # If we can't parse the JSON, include the raw body
            details += f"\nRaw error body: {error.body}"
        except Exception as e:
            # Catch any other exceptions during parsing
            details += f"\nError parsing error body: {str(e)}"
    # Include request information if available
    if hasattr(error, "request") and error.request:
        if hasattr(error.request, "method") and hasattr(error.request, "url"):
            details += f"\nRequest: {error.request.method} {error.request.url}"
        # Include a truncated version of the request content if available
        if hasattr(error.request, "content") and error.request.content:
            content = error.request.content
            if isinstance(content, bytes):
                try:
                    content = content.decode("utf-8")
                except UnicodeDecodeError:
                    content = str(content)
            details += f"\nRequest content: {content}"
    return details
