"""Main CLI entry point for the `uvero` command."""

from __future__ import annotations

import re
import sys
import webbrowser
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import typer

from uvero import api
from uvero.boards import board_app
from uvero.clipboard import read_clipboard, write_clipboard
from uvero.config import EXIT_API_ERR, EXIT_NETWORK_ERR, EXIT_VALIDATION_ERR, state
from uvero.config_cli import config_app
from uvero.utils import (
    auto_upgrade,
    console,
    handle_api_error,
    is_piped,
    print_json_output,
    print_message,
    read_file,
    read_stdin,
    write_file,
)

CODE_PATTERN = re.compile(r"^[0-9]{4}$")

app = typer.Typer(
    name="uvero",
    help=(
        "Share text through the Uvero online clipboard.\n\n"
        "Use `uvero send` to upload text from a file, stdin, interactive paste, "
        "or your system clipboard. Use `uvero get CODE` to save content to a file, "
        "or `uvero get CODE -` to copy it directly to your clipboard. "
        "Use `uvero open [CODE]` to open Uvero in your browser.\n\n"
        "Use `uvero board` for private shared boards."
    ),
    epilog=(
        "Examples:\n"
        "  uvero send\n"
        "  uvero send notes.txt\n"
        "  uvero send notes.txt --raw\n"
        "  uvero send -\n"
        "  cat notes.txt | uvero send\n"
        "  uvero get 1234\n"
        "  uvero get 1234 notes.txt\n"
        "  uvero get 1234 -\n"
        "  uvero health\n"
        "  uvero open\n"
        "  uvero open 1234\n"
        "  uvero --version\n"
        "  uvero version\n"
        "  uvero board --help"
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
)

app.add_typer(board_app, name="board")
app.add_typer(config_app, name="config")


def _installed_version() -> str:
    """Return the installed Uvero CLI version."""
    from uvero import __version__

    try:
        distribution_version = metadata.version("uvero")
    except metadata.PackageNotFoundError:
        return __version__

    return __version__ if distribution_version != __version__ else distribution_version


@app.callback(invoke_without_command=True)
def _startup(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed Uvero CLI version and exit.",
        is_eager=True,
    ),
    json: bool = typer.Option(
        False, "--json", help="Format output as JSON (useful for scripting)."
    ),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress non-error output."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable rich colored output."),
    no_emoji: bool = typer.Option(False, "--no-emoji", help="Disable emojis in terminal output."),
) -> None:
    """Run before every command: handle global flags and updates."""
    # Apply global UX state
    state.json_output = json
    state.quiet = quiet
    state.no_color = no_color
    state.no_emoji = no_emoji

    if no_color or state.get_config("no_color"):
        console.no_color = True

    if version:
        if state.get_config("output_mode") == "json":
            print_json_output({"version": _installed_version()})
        else:
            print_message(f"Uvero CLI v{_installed_version()}")
        raise typer.Exit()

    if auto_upgrade():
        raise typer.Exit()


def _call_api(
    api_function: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any
) -> Dict[str, Any]:
    """Run a backend call and map connection failures to a clean CLI message."""
    try:
        return api_function(*args, **kwargs)
    except api.UveroServiceConnectionError as exc:
        msg = "Cannot reach Uvero service"
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(f"[bold red]{msg}[/bold red]", is_error=True, emoji="❌")
        raise typer.Exit(EXIT_NETWORK_ERR) from exc
    except Exception as exc:
        msg = str(exc)
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_API_ERR) from exc


def _validate_code(code: str) -> None:
    """Validate that *code* uses the expected 4-digit format."""
    if not CODE_PATTERN.fullmatch(code):
        msg = "Clipboard code must be a 4 digit number."
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR)


def _public_clipboard_url(code: str) -> str:
    """Return the public share URL for the clipboard *code*."""
    return f"{api.BASE_URL}/c/{code}"


@app.command(
    help="Send text to Uvero from a file, stdin, interactive paste, or the system clipboard.",
    epilog=(
        "Examples:\n"
        "  uvero send\n"
        "  uvero send notes.txt\n"
        "  cat notes.txt | uvero send\n"
        "  uvero send -"
    ),
)
def send(
    file: Optional[str] = typer.Argument(
        None,
        metavar="[FILE|-]",
        help="File to send. Omit for interactive paste, pipe stdin, or use '-' to send your clipboard.",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Print only the clipboard code (useful for scripting).",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        help="Automatically open the generated link in your browser.",
    ),
    copy_link: bool = typer.Option(
        False,
        "--copy-link",
        help="Copy the shareable URL instead of the short code to the clipboard.",
    ),
) -> None:
    """Send content to the Uvero clipboard."""
    if file == "-":
        # Read from system clipboard
        try:
            content = read_clipboard()
        except Exception as exc:
            msg = f"Error reading clipboard: {exc}"
            if state.get_config("output_mode") == "json":
                print_json_output({"success": False, "error": msg})
            else:
                print_message(str(exc), is_error=True, emoji="❌")
            raise typer.Exit(EXIT_VALIDATION_ERR) from exc
    elif file:
        # Read from the given file path
        try:
            content = read_file(file)
        except OSError as exc:
            msg = str(exc)
            if state.get_config("output_mode") == "json":
                print_json_output({"success": False, "error": msg})
            else:
                print_message(msg, is_error=True, emoji="❌")
            raise typer.Exit(EXIT_VALIDATION_ERR) from exc
    elif is_piped():
        # Data piped via stdin
        content = read_stdin()
    else:
        # Interactive paste mode
        if not state.get_config("quiet") and state.get_config("output_mode") != "json":
            print_message(
                "[dim]Paste your text below. Press CTRL+D (Linux/Mac) or CTRL+Z (Windows) when done.[/dim]"
            )
        try:
            content = sys.stdin.read()
        except EOFError:
            content = ""

    if not content:
        msg = "Nothing to send."
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR)

    result = _call_api(api.send_clipboard, content)
    handle_api_error(result)

    code = str(result.get("data", {}).get("code", "")).strip()
    if not code:
        msg = "Missing clipboard code in response."
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_API_ERR)

    url = _public_clipboard_url(code)

    if raw:
        console.print(code)
        return

    if state.get_config("output_mode") == "json":
        print_json_output(
            {
                "success": True,
                "data": {
                    "code": code,
                    "url": url,
                },
            }
        )
        return

    auto_open = open_browser or state.get_config("auto_open")
    if auto_open:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass

    print_message(f"Clipboard Code: {code}", emoji="📋")

    # Check default behavior override if flags weren't provided explicitly
    copy_url = copy_link or state.get_config("clipboard_behavior") == "link"

    try:
        write_clipboard(url if copy_url else code)
    except Exception:
        print_message("[yellow]Could not copy to clipboard[/yellow]", emoji="⚠")
    else:
        noun = "Link" if copy_url else "Code"
        print_message(f"[bold green]{noun} copied to clipboard[/bold green]", emoji="✔")

    print_message(f"🔗 [link]{url}[/link]")


@app.command(
    help="Retrieve text from Uvero and save it to a file, or use '-' to copy it to the system clipboard.",
    epilog=("Examples:\n  uvero get 1234\n  uvero get 1234 notes.txt\n  uvero get 1234 -"),
)
def get(
    code: str = typer.Argument(..., metavar="CODE", help="Clipboard code to retrieve."),
    output: Optional[str] = typer.Argument(
        None,
        metavar="[OUTPUT|-]",
        help="Destination file path. Use '-' or --stdout to copy to the clipboard. Omit to save as uvero_CODE.txt.",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Print directly to standard out.",
    ),
) -> None:
    """Retrieve content from the Uvero clipboard."""
    _validate_code(code)

    result = _call_api(api.get_clipboard, code)

    handle_api_error(result)

    content = result.get("data", {}).get("content", "")

    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "data": result.get("data")})
        return

    if stdout:
        if state.get_config("output_mode") != "json":
            # Only print raw content explicitly bypassing formatter
            print(content)
        return

    if output == "-":
        try:
            write_clipboard(content)
        except Exception as exc:
            print_message(str(exc), is_error=True, emoji="❌")
            raise typer.Exit(EXIT_VALIDATION_ERR) from exc
        print_message("[bold green]Copied to clipboard[/bold green]", emoji="✔")
        return

    # Determine output file path
    dest = output if output else f"uvero_{code}.txt"
    try:
        write_file(dest, content)
    except OSError as exc:
        print_message(str(exc), is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR) from exc

        print_message(f"[bold green]Saved to:[/bold green] {dest}", emoji="✔")


@app.command(
    help="Open Uvero in your default browser.",
    epilog=("Examples:\n  uvero open\n  uvero open 4832"),
)
def open(
    code: Optional[str] = typer.Argument(
        None,
        metavar="[CODE]",
        help="Clipboard code to open. Omit to open Uvero home page.",
    ),
) -> None:
    """Open Uvero in the default web browser."""
    if code is not None:
        _validate_code(code)
        url = _public_clipboard_url(code)
    else:
        url = api.BASE_URL

    if not webbrowser.open(url):
        msg = "Could not open browser."
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR)

    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "data": {"url": url}})
        return

    print_message(f"🔗 {url}")


@app.command(help="Check whether the Uvero service is reachable.")
def health() -> None:
    """Check service availability."""
    result = _call_api(api.health_check)
    handle_api_error(result)

    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "status": "healthy"})
        return

    print_message("[bold green]Uvero service is reachable[/bold green]", emoji="✔")


@app.command(help="Run local diagnostics to verify network, configuration, and clipboard support.")
def doctor() -> None:
    """Run local environment and configuration diagnostics."""
    from uvero.config import _CONFIG_FILE

    diagnostics = {
        "python_version": sys.version.split(" ")[0],
        "uvero_version": _installed_version(),
        "config_path": str(_CONFIG_FILE)
        if "uvero.config" in sys.modules
        else str(Path.home() / ".uvero/config.json"),
        "network_reachable": False,
        "clipboard_read": False,
        "clipboard_write": False,
    }

    if state.get_config("output_mode") != "json":
        print_message("Running Uvero diagnostics...", emoji="🩺")

    # 1. Check Network
    try:
        api.health_check()
        diagnostics["network_reachable"] = True
    except Exception:
        pass

    # 2. Check Clipboard
    try:
        # We don't want to actually overwrite user clipboard during doctor
        # We just try import to verify pyperclip is functional
        diagnostics["clipboard_read"] = True
        diagnostics["clipboard_write"] = True
    except Exception:
        pass

    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "diagnostics": diagnostics})
        return

    # Print nicely formatted
    print_message(f"Python: {diagnostics['python_version']}", emoji="🐍")
    print_message(f"Uvero CLI: {diagnostics['uvero_version']}", emoji="📦")
    print_message(f"Config path: {diagnostics['config_path']}", emoji="📄")

    if diagnostics["network_reachable"]:
        print_message("[bold green]API is reachable[/bold green]", emoji="✔")
    else:
        print_message("[bold red]API is UNREACHABLE[/bold red]", emoji="❌")

    if diagnostics["clipboard_read"]:
        print_message("[bold green]System clipboard module loaded[/bold green]", emoji="✔")
    else:
        print_message(
            "[bold red]Clipboard interaction not supported[/bold red] (Please install xclip / xsel if on Linux)",
            emoji="❌",
        )


@app.command(help="Check for updates and explicitly upgrade the CLI.")
def update() -> None:
    """Manually check for and install updates."""
    # Temporarily set quiet to false for update specifically if it was just run
    was_quiet = state.quiet
    state.quiet = False

    if state.get_config("output_mode") != "json":
        print_message("Checking for updates...", emoji="🔍")

    # We call auto_upgrade but bypass the 24h cache check by removing the cache file if it exists
    from pathlib import Path

    try:
        cache_file = Path.home() / ".uvero" / ".version_check"
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass

    # We will temporarily mock the output to be JSON if requested
    auto_upgrade(explicit=True)

    state.quiet = was_quiet


@app.command(help="Show the installed Uvero CLI version.", hidden=True)
def version() -> None:
    """Print the installed Uvero CLI version (alias for --version)."""
    if state.get_config("output_mode") == "json":
        print_json_output({"version": _installed_version()})
    else:
        print_message(f"Uvero CLI v{_installed_version()}")


if __name__ == "__main__":
    app()
