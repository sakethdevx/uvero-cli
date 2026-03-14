"""Shared utilities used across CLI commands."""

import os
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


# ---------------------------------------------------------------------------
# Auto-upgrade helpers
# ---------------------------------------------------------------------------

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional

_CACHE_DIR = Path.home() / ".uvero"
_CACHE_FILE = _CACHE_DIR / ".version_check"
_CHECK_INTERVAL = 86400  # 24 hours in seconds
_PYPI_URL = "https://pypi.org/pypi/uvero/json"


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
    """Fetch the latest published version from PyPI (returns None on any failure)."""
    try:
        with urllib.request.urlopen(_PYPI_URL, timeout=5) as resp:
            data = json.load(resp)
            return data["info"]["version"]
    except Exception:
        return None


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _in_virtualenv() -> bool:
    return bool(
        hasattr(sys, "real_prefix")
        or getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    )


def auto_upgrade() -> None:
    """Check PyPI at most once per day and auto-upgrade if a newer version exists."""
    from uvero import __version__

    if os.environ.get("UVERO_AUTO_UPGRADE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return

    cache = _read_cache()
    now = time.time()

    # Use cached latest version if the cache is fresh
    if now - cache.get("checked_at", 0) < _CHECK_INTERVAL:
        latest = cache.get("latest")
    else:
        latest = _latest_pypi_version()
        _write_cache({"checked_at": now, "latest": latest})

    if not latest:
        return

    if _parse_version(latest) <= _parse_version(__version__):
        return  # already up to date

    console.print(
        f"[dim]🔄 New version available: [bold]v{latest}[/bold]. Upgrading…[/dim]"
    )
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

        console.print(
            f"[bold green]✔ Upgraded to v{latest}[/bold green] "
            "[dim](takes effect on next run)[/dim]"
        )
        # Invalidate cache so we don't re-upgrade immediately
        _write_cache({"checked_at": now, "latest": latest})
    except Exception:
        console.print(
            f"[yellow]⚠ Could not auto-upgrade. Run:[/yellow] "
            f"[bold]{sys.executable} -m pip install --upgrade --no-cache-dir --force-reinstall uvero[/bold]"
        )
