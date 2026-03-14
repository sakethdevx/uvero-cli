"""Main CLI entry point for the `uvero` command."""

from __future__ import annotations

import re
import sys
import webbrowser
from importlib import metadata
from typing import Optional

import typer
from rich.console import Console

from uvero import api
from uvero.boards import board_app
from uvero.clipboard import read_clipboard, write_clipboard
from uvero.utils import auto_upgrade, handle_api_error, is_piped, read_file, read_stdin, write_file

console = Console()
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
) -> None:
    """Run before every command: check for updates."""
    if version:
        console.print(f"Uvero CLI v{_installed_version()}")
        raise typer.Exit()

    auto_upgrade()


def _call_api(api_function, *args, **kwargs) -> dict:
    """Run a backend call and map connection failures to a clean CLI message."""
    try:
        return api_function(*args, **kwargs)
    except api.UveroServiceConnectionError:
        console.print("[bold red]❌ Cannot reach Uvero service[/bold red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)


def _validate_code(code: str) -> None:
    """Validate that *code* uses the expected 4-digit format."""
    if not CODE_PATTERN.fullmatch(code):
        console.print("[bold red]❌ Clipboard code must be a 4 digit number.[/bold red]")
        raise typer.Exit(1)


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
):
    """Send content to the Uvero clipboard."""
    if file == "-":
        # Read from system clipboard
        try:
            content = read_clipboard()
        except Exception as exc:
            console.print(f"[bold red]❌ Error reading clipboard:[/bold red] {exc}")
            raise typer.Exit(1)
    elif file:
        # Read from the given file path
        try:
            content = read_file(file)
        except OSError as exc:
            console.print(f"[bold red]❌ Error:[/bold red] {exc}")
            raise typer.Exit(1)
    elif is_piped():
        # Data piped via stdin
        content = read_stdin()
    else:
        # Interactive paste mode
        console.print("[dim]Paste your text below. Press CTRL+D (Linux/Mac) or CTRL+Z (Windows) when done.[/dim]")
        try:
            content = sys.stdin.read()
        except EOFError:
            content = ""

    if not content:
        console.print("[bold red]❌ Error:[/bold red] Nothing to send.")
        raise typer.Exit(1)

    result = _call_api(api.send_clipboard, content)
    handle_api_error(result)

    code = str(result.get("data", {}).get("code", "")).strip()
    if not code:
        console.print("[bold red]❌ Error:[/bold red] Missing clipboard code in response.")
        raise typer.Exit(1)

    if raw:
        console.print(code)
        return

    console.print(f"📋 Clipboard Code: {code}")
    try:
        write_clipboard(code)
    except Exception:
        console.print("[yellow]⚠ Could not copy code to clipboard[/yellow]")
    else:
        console.print("[bold green]✔ Code copied to clipboard[/bold green]")

    console.print(f"🔗 [link]{_public_clipboard_url(code)}[/link]")


@app.command(
    help="Retrieve text from Uvero and save it to a file, or use '-' to copy it to the system clipboard.",
    epilog=(
        "Examples:\n"
        "  uvero get 1234\n"
        "  uvero get 1234 notes.txt\n"
        "  uvero get 1234 -"
    ),
)
def get(
    code: str = typer.Argument(..., metavar="CODE", help="Clipboard code to retrieve."),
    output: Optional[str] = typer.Argument(
        None,
        metavar="[OUTPUT|-]",
        help="Destination file path. Use '-' to copy to the clipboard. Omit to save as uvero_CODE.txt.",
    ),
):
    """Retrieve content from the Uvero clipboard."""
    _validate_code(code)

    result = _call_api(api.get_clipboard, code)

    handle_api_error(result)

    content = result.get("data", {}).get("content", "")

    if output == "-":
        try:
            write_clipboard(content)
        except Exception as exc:
            console.print(f"[bold red]❌ Error copying to clipboard:[/bold red] {exc}")
            raise typer.Exit(1)
        console.print("[bold green]✔ Copied to clipboard[/bold green]")
        return

    # Determine output file path
    dest = output if output else f"uvero_{code}.txt"
    try:
        write_file(dest, content)
    except OSError as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    console.print(f"[bold green]✔ Saved to:[/bold green] {dest}")


@app.command(
    help="Open Uvero in your default browser.",
    epilog=(
        "Examples:\n"
        "  uvero open\n"
        "  uvero open 4832"
    ),
)
def open(
    code: Optional[str] = typer.Argument(
        None,
        metavar="[CODE]",
        help="Clipboard code to open. Omit to open Uvero home page.",
    ),
):
    """Open Uvero in the default web browser."""
    if code is not None:
        _validate_code(code)
        url = _public_clipboard_url(code)
    else:
        url = api.BASE_URL

    if not webbrowser.open(url):
        console.print("[bold red]❌ Error:[/bold red] Could not open browser.")
        raise typer.Exit(1)

    console.print(f"🔗 {url}")


@app.command(help="Check whether the Uvero service is reachable.")
def health() -> None:
    """Check service availability."""
    result = _call_api(api.health_check)
    handle_api_error(result)
    console.print("[bold green]✔ Uvero service is reachable[/bold green]")


@app.command(help="Show the installed Uvero CLI version.")
def version() -> None:
    """Print the installed Uvero CLI version."""
    console.print(f"Uvero CLI v{_installed_version()}")


if __name__ == "__main__":
    app()
