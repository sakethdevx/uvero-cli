"""API layer – all communication with the Uvero backend."""

from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("UVERO_BASE_URL", "https://uvero.app").rstrip("/")


class UveroServiceConnectionError(RuntimeError):
    """Raised when the Uvero service cannot be reached over the network."""


class UveroApiError(RuntimeError):
    """Raised when the Uvero API responds with an error or invalid payload."""


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


def _request(method: str, path: str, *, timeout: int, **kwargs) -> requests.Response:
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
    except requests.exceptions.RequestException as exc:
        raise UveroApiError(str(exc)) from exc


def _extract_error_message(payload: object, status_code: int) -> str:
    if isinstance(payload, dict):
        error = payload.get("error") or payload.get("message")
        if isinstance(error, str) and error.strip():
            return error

    return f"Uvero returned HTTP {status_code}."


def _request_json(method: str, path: str, *, timeout: int, **kwargs) -> dict:
    """Execute an HTTP request and return a validated JSON object."""
    response = _request(method, path, timeout=timeout, **kwargs)

    try:
        payload = response.json()
    except ValueError as exc:
        if response.ok:
            raise UveroApiError("Uvero returned an invalid response.") from exc
        raise UveroApiError(f"Uvero returned HTTP {response.status_code}.") from exc

    if not isinstance(payload, dict):
        raise UveroApiError("Uvero returned an unexpected response.")

    if not response.ok:
        raise UveroApiError(_extract_error_message(payload, response.status_code))

    return payload


def send_clipboard(content: str) -> dict:
    """Upload *content* to the clipboard service and return the JSON response."""
    return _request_json(
        "POST",
        "/api/clipboard/send",
        json={"content": content},
        timeout=15,
    )


def get_clipboard(code: str) -> dict:
    """Fetch clipboard entry identified by *code* and return the JSON response."""
    return _request_json(
        "GET",
        f"/api/clipboard/get/{code}",
        timeout=15,
    )


def create_board(password: str | None = None) -> dict:
    """Create a new private board and return the JSON response."""
    payload: dict = {}
    if password:
        payload["password"] = password
    return _request_json(
        "POST",
        "/api/clipboard/board/create",
        json=payload,
        timeout=15,
    )


def send_board(board: str, content: str, password: str | None = None) -> dict:
    """Send *content* to *board* and return the JSON response."""
    payload: dict = {"board": board, "content": content}
    if password:
        payload["password"] = password
    return _request_json(
        "POST",
        "/api/clipboard/board/send",
        json=payload,
        timeout=15,
    )


def get_board(board: str, password: str | None = None) -> dict:
    """Retrieve content from *board* and return the JSON response."""
    params: dict = {}
    if password:
        params["password"] = password
    return _request_json(
        "GET",
        f"/api/clipboard/board/get/{board}",
        params=params,
        timeout=15,
    )


def health_check() -> dict:
    """Call the CLI health endpoint and return the JSON response."""
    return _request_json(
        "GET",
        "/api/clipboard/cli-health",
        timeout=10,
    )
