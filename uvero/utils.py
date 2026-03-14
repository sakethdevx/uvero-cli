"""Shared utilities used across CLI commands."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from rich.console import Console

from uvero.config import EXIT_API_ERR, state

console = Console()


def print_message(message: str, is_error: bool = False, emoji: str = "") -> None:
    """Print a rich formatted message respecting global UX flags.

    If `--quiet` is enabled, only process errors.
    If `--no-emoji` is enabled, strip the emoji.
    """
    if state.get_config("quiet") and not is_error:
        return

    emoji_prefix = f"{emoji} " if emoji and not state.get_config("no_emoji") else ""
    formatted_message = f"{emoji_prefix}{message}"

    if is_error:
        import sys
        
        console.stderr = True
        console.print(f"[bold red]{emoji_prefix}Error:[/bold red] {message}")
        console.stderr = False
    else:
        console.print(formatted_message)


def print_json_output(data: Dict[str, Any]) -> None:
    """Print JSON output mapping to stdout."""
    # Ensure stdout isn't colored unless explicitly forcing rich JSON
    # Python json.dumps guarantees machine readability
    print(json.dumps(data, indent=2))


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


def handle_api_error(response: Dict[str, Any]) -> None:
    """Print a rich error message and raise SystemExit if the API returned an error."""
    if not response.get("success", True):
        error_msg = response.get("error", "Unknown error")
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": error_msg})
        else:
            print_message(error_msg, is_error=True, emoji="❌")
        raise SystemExit(EXIT_API_ERR)


# ---------------------------------------------------------------------------
# Auto-upgrade helpers
# ---------------------------------------------------------------------------

_CACHE_DIR = Path.home() / ".uvero"
_CACHE_FILE = _CACHE_DIR / ".version_check"
_CHECK_INTERVAL = 86400  # 24 hours in seconds
_PYPI_URL = "https://pypi.org/pypi/uvero/json"


def _read_cache() -> Dict[str, Any]:
    try:
        return dict(json.loads(_CACHE_FILE.read_text()))
    except Exception:
        return {}


def _write_cache(data: Dict[str, Any]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _latest_pypi_version() -> Optional[str]:
    """Fetch the latest published version from PyPI (returns None on any failure)."""
    try:
        with urllib.request.urlopen(_PYPI_URL, timeout=5) as resp:
            data = dict(json.load(resp))
            return str(data["info"]["version"])
    except Exception:
        return None


def _parse_version(v: str) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _in_virtualenv() -> bool:
    return bool(
        hasattr(sys, "real_prefix") or getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    )


def auto_upgrade(explicit: bool = False) -> None:
    """Check PyPI at most once per day and auto-upgrade if a newer version exists."""
    from uvero import __version__
    from uvero.config import state

    if not explicit and os.environ.get("UVERO_AUTO_UPGRADE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return

    cache = _read_cache()
    now = time.time()

    # Use cached latest version if the cache is fresh (only if not explicit)
    if not explicit and now - cache.get("checked_at", 0) < _CHECK_INTERVAL:
        latest = cache.get("latest")
    else:
        latest = _latest_pypi_version()
        _write_cache({"checked_at": now, "latest": latest})

    if not latest:
        if explicit:
            msg = "Could not check for updates right now."
            if state.get_config("output_mode") == "json":
                print_json_output({"success": False, "error": msg})
            else:
                print_message(msg, is_error=True, emoji="❌")
        return

    if _parse_version(latest) <= _parse_version(__version__):
        if explicit:
            if state.get_config("output_mode") == "json":
                print_json_output({"success": True, "up_to_date": True, "version": latest})
            else:
                print_message(
                    f"[bold green]You are already on the latest version ({latest})[/bold green]",
                    emoji="✔",
                )
        return  # already up to date

    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "upgrading_to": latest, "current_version": __version__})
    else:
        print_message(f"[dim]🔄 New version available: [bold]v{latest}[/bold]. Upgrading…[/dim]")

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

        if state.get_config("output_mode") != "json":
            print_message(
                f"[bold green]Upgraded to v{latest}[/bold green] [dim](takes effect on next run)[/dim]",
                emoji="✔",
            )
        # Invalidate cache so we don't re-upgrade immediately
        _write_cache({"checked_at": now, "latest": latest})
    except Exception:
        msg = f"Could not auto-upgrade. Run: {sys.executable} -m pip install --upgrade --no-cache-dir --force-reinstall uvero"
        if state.get_config("output_mode") == "json" and explicit:
            print_json_output({"success": False, "error": msg})
        elif state.get_config("output_mode") != "json":
            print_message(f"[yellow]{msg}[/yellow]", emoji="⚠")
