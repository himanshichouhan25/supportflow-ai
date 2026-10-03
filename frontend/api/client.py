"""
frontend/api/client.py — Centralized Frontend API Client for SupportFlow AI.
"""

import os
from typing import Any
import requests

DEFAULT_API_URL = "http://127.0.0.1:8000"


class APIClient:
    """Centralized API client for communicating with FastAPI backend."""

    def __init__(self, base_url: str | None = None, timeout: int = 15) -> None:
        self.base_url = (base_url or os.getenv("SUPPORTFLOW_API_URL") or DEFAULT_API_URL).rstrip("/")
        self.timeout = timeout

    def post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute HTTP POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(url, json=json_data or {}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "status": "FAILED",
                "final_response": f"Unable to reach backend API ({url}): {exc}",
                "error": str(exc),
            }

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Execute HTTP GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            return {"error": str(exc)}


api_client = APIClient()
