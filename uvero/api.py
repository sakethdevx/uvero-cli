"""API layer – all communication with the Uvero backend."""

from __future__ import annotations

from typing import Any, Dict

import requests

BASE_URL = "https://uvero.app"


class UveroServiceConnectionError(RuntimeError):
    """Raised when the Uvero service cannot be reached over the network."""


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


def _request(method: str, path: str, *, timeout: int, **kwargs: Any) -> requests.Response:
    """Execute an HTTP request and map network failures to a dedicated error."""
    try:
        return requests.request(
            method,
            _url(path),
            timeout=timeout,
            **kwargs,
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        raise UveroServiceConnectionError("Cannot reach Uvero service") from exc


def send_clipboard(content: str) -> Dict[str, Any]:
    """Upload *content* to the clipboard service and return the JSON response."""
    response = _request(
        "POST",
        "/api/clipboard/send",
        json={"content": content},
        timeout=15,
    )
    response.raise_for_status()
    return dict(response.json())


def get_clipboard(code: str) -> Dict[str, Any]:
    """Fetch clipboard entry identified by *code* and return the JSON response."""
    response = _request(
        "GET",
        f"/api/clipboard/get/{code}",
        timeout=15,
    )
    response.raise_for_status()
    return dict(response.json())


def create_board(password: str | None = None) -> Dict[str, Any]:
    """Create a new private board and return the JSON response."""
    payload: Dict[str, Any] = {}
    if password:
        payload["password"] = password
    response = _request(
        "POST",
        "/api/clipboard/board/create",
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return dict(response.json())


def send_board(board: str, content: str, password: str | None = None) -> Dict[str, Any]:
    """Send *content* to *board* and return the JSON response."""
    payload: Dict[str, Any] = {"board": board, "content": content}
    if password:
        payload["password"] = password
    response = _request(
        "POST",
        "/api/clipboard/board/send",
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return dict(response.json())


def get_board(board: str, password: str | None = None) -> Dict[str, Any]:
    """Retrieve content from *board* and return the JSON response."""
    params: Dict[str, Any] = {}
    if password:
        params["password"] = password
    response = _request(
        "GET",
        f"/api/clipboard/board/get/{board}",
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return dict(response.json())


def health_check() -> Dict[str, Any]:
    """Call the CLI health endpoint and return the JSON response."""
    response = _request(
        "GET",
        "/api/clipboard/cli-health",
        timeout=10,
    )
    response.raise_for_status()
    return dict(response.json())
