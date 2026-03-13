"""Shared utilities used across CLI commands."""

import sys
from pathlib import Path

from rich.console import Console

console = Console()


def read_stdin() -> str:
    """Read all text from standard input (piped or interactive paste mode)."""
    return sys.stdin.read()


def is_piped() -> bool:
    """Return True when data is being piped into the process via stdin."""
    return not sys.stdin.isatty()


def read_file(path: str) -> str:
    """Read and return the contents of the file at *path*."""
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> None:
    """Write *content* to the file at *path*."""
    Path(path).write_text(content, encoding="utf-8")


def handle_api_error(response: dict) -> None:
    """Print a rich error message and raise SystemExit if the API returned an error."""
    if not response.get("success", True):
        error_msg = response.get("error", "Unknown error")
        console.print(f"[bold red]❌ Error:[/bold red] {error_msg}")
        raise SystemExit(1)
