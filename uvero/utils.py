"""Shared utilities used across CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from uvero import api
from uvero.clipboard import read_clipboard, write_clipboard

console = Console()


class UveroCliUsageError(ValueError):
    """Raised when a command is used with an unsupported combination of inputs."""


def abort(message: str, *, exit_code: int = 1) -> None:
    """Print a CLI error message and exit."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(exit_code)


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
    """Exit cleanly when the API responds with a logical error payload."""
    if not response.get("success", True):
        error_msg = response.get("error", "Unknown error")
        abort(str(error_msg))


def call_api(api_function: Callable[..., dict], *args, **kwargs) -> dict:
    """Run an API call and map failures to clean CLI messages."""
    try:
        response = api_function(*args, **kwargs)
    except api.UveroServiceConnectionError:
        abort("Cannot reach the Uvero service.")
    except api.UveroApiError as exc:
        abort(str(exc))
    except Exception as exc:
        abort(str(exc))

    handle_api_error(response)
    return response


def warn_deprecated_usage(old: str, new: str) -> None:
    """Show a soft deprecation warning for legacy command forms."""
    console.print(f"[yellow]Warning:[/yellow] {old} is deprecated. Use {new} instead.")


def render_summary(title: str, rows: list[tuple[str, str]], *, style: str = "green") -> None:
    """Render a compact summary panel for successful commands."""
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()

    for label, value in rows:
        table.add_row(f"{label}:", value)

    console.print(Panel.fit(table, title=title, border_style=style))


def read_interactive_text(prompt: str) -> str:
    """Prompt the user and collect text from stdin until EOF."""
    console.print(f"[dim]{prompt}[/dim]")
    try:
        return sys.stdin.read()
    except EOFError:
        return ""


def read_text_source(source: Optional[str], value: Optional[str], *, interactive_prompt: str) -> str:
    """Resolve a human-friendly source selector into text content."""
    normalized = source.strip().lower() if source else None

    if normalized is None:
        return read_stdin() if is_piped() else read_interactive_text(interactive_prompt)

    if normalized == "-":
        warn_deprecated_usage("`-` for clipboard", "`clipboard`")
        return read_clipboard()

    if normalized == "clipboard":
        if value:
            raise UveroCliUsageError("`clipboard` does not take an extra value.")
        return read_clipboard()

    if normalized in {"paste", "interactive"}:
        if value:
            raise UveroCliUsageError("`paste` does not take an extra value.")
        return read_interactive_text(interactive_prompt)

    if normalized == "stdin":
        if value:
            raise UveroCliUsageError("`stdin` does not take an extra value.")
        return read_stdin()

    if normalized == "file":
        if not value:
            raise UveroCliUsageError("Use `file <path>` to send a file.")
        return read_file(value)

    if value:
        raise UveroCliUsageError(
            "Use `clipboard`, `stdin`, `paste`, or `file <path>` for the input source."
        )

    return read_file(source)


def resolve_text_target(
    target: Optional[str],
    value: Optional[str],
    *,
    default_mode: str,
    default_path: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Resolve a human-friendly destination selector into a concrete target."""
    normalized = target.strip().lower() if target else None

    if normalized is None:
        if default_mode == "file":
            return ("file", default_path)
        return (default_mode, None)

    if normalized == "-":
        warn_deprecated_usage("`-` for clipboard", "`clipboard`")
        return ("clipboard", None)

    if normalized == "clipboard":
        if value:
            raise UveroCliUsageError("`clipboard` does not take an extra value.")
        return ("clipboard", None)

    if normalized == "stdout":
        if value:
            raise UveroCliUsageError("`stdout` does not take an extra value.")
        return ("stdout", None)

    if normalized == "file":
        if not value:
            raise UveroCliUsageError("Use `file <path>` to choose an output file.")
        return ("file", value)

    if value:
        raise UveroCliUsageError(
            "Use `clipboard`, `stdout`, or `file <path>` for the destination."
        )

    return ("file", target)


def deliver_text(content: str, mode: str, destination: Optional[str] = None) -> str:
    """Write content to the selected destination and return a short label for it."""
    if mode == "clipboard":
        write_clipboard(content)
        return "clipboard"

    if mode == "stdout":
        console.print(content, markup=False, highlight=False, soft_wrap=True)
        return "terminal"

    if mode == "file" and destination:
        write_file(destination, content)
        return destination

    raise UveroCliUsageError("Unsupported destination.")


# ---------------------------------------------------------------------------
# Update helpers
# ---------------------------------------------------------------------------

_CACHE_DIR = Path.home() / ".uvero"
_CACHE_FILE = _CACHE_DIR / ".version_check"
_CHECK_INTERVAL = 86400  # 24 hours in seconds
_PYPI_URL = "https://pypi.org/pypi/uvero/json"
_DISABLED_VALUES = {"0", "false", "no", "off"}


def _read_cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        return {}


def _write_cache(data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _latest_pypi_version() -> Optional[str]:
    """Fetch the latest published version from PyPI."""
    try:
        with urllib.request.urlopen(_PYPI_URL, timeout=5) as resp:
            data = json.load(resp)
            return data["info"]["version"]
    except Exception:
        return None


def _parse_version(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except Exception:
        return (0,)


def _in_virtualenv() -> bool:
    return bool(
        hasattr(sys, "real_prefix")
        or getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    )


def _update_checks_enabled() -> bool:
    auto_upgrade_value = os.environ.get("UVERO_AUTO_UPGRADE", "1").strip().lower()
    update_check_value = os.environ.get("UVERO_UPDATE_CHECK", "1").strip().lower()
    return auto_upgrade_value not in _DISABLED_VALUES and update_check_value not in _DISABLED_VALUES


def _latest_cached_or_live_version() -> Optional[str]:
    cache = _read_cache()
    now = time.time()

    if now - cache.get("checked_at", 0) < _CHECK_INTERVAL:
        return cache.get("latest")

    latest = _latest_pypi_version()
    _write_cache({"checked_at": now, "latest": latest})
    return latest


def available_update_version() -> Optional[str]:
    """Return the latest version if it is newer than the installed one."""
    from uvero import __version__

    latest = _latest_cached_or_live_version()
    if not latest:
        return None

    if _parse_version(latest) <= _parse_version(__version__):
        return None

    return latest


def notify_if_update_available() -> None:
    """Show a lightweight update notice without performing any installs."""
    if not _update_checks_enabled():
        return

    latest = available_update_version()
    if latest:
        console.print(
            f"[dim]Update available: v{latest}. Run `uvero update` when you want to install it.[/dim]"
        )


def install_update() -> None:
    """Install the latest published version of Uvero."""
    latest = available_update_version()
    if not latest:
        console.print("[bold green]Uvero CLI is already up to date.[/bold green]")
        return

    console.print(f"[dim]Installing Uvero CLI v{latest}...[/dim]")
    upgrade_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--no-cache-dir",
        "--force-reinstall",
        "uvero",
    ]

    try:
        try:
            subprocess.run(upgrade_cmd, check=True, timeout=120)
        except subprocess.CalledProcessError:
            if _in_virtualenv():
                raise

            subprocess.run([*upgrade_cmd, "--user"], check=True, timeout=120)
    except Exception:
        abort(
            "Could not update automatically. Run "
            f"`{sys.executable} -m pip install --upgrade --no-cache-dir --force-reinstall uvero`."
        )

    console.print(
        f"[bold green]Updated to v{latest}[/bold green] [dim](takes effect on the next run)[/dim]"
    )
    _write_cache({"checked_at": time.time(), "latest": latest})
