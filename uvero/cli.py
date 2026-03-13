"""Main CLI entry point for the `uvero` command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from uvero import api
from uvero.boards import board_app
from uvero.clipboard import read_clipboard, write_clipboard
from uvero.utils import handle_api_error, is_piped, read_file, read_stdin, write_file

console = Console()

app = typer.Typer(
    name="uvero",
    help=(
        "Share text through the Uvero online clipboard.\n\n"
        "Use `uvero send` to upload text from a file, stdin, interactive paste, "
        "or your system clipboard. Use `uvero get CODE` to save content to a file, "
        "or `uvero get CODE -` to copy it directly to your clipboard.\n\n"
        "Use `uvero board` for private shared boards."
    ),
    epilog=(
        "Examples:\n"
        "  uvero send\n"
        "  uvero send notes.txt\n"
        "  uvero send -\n"
        "  cat notes.txt | uvero send\n"
        "  uvero get 1234\n"
        "  uvero get 1234 notes.txt\n"
        "  uvero get 1234 -\n"
        "  uvero board --help"
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
)

app.add_typer(board_app, name="board")


def _check_health() -> None:
    """Silently verify that the Uvero service is reachable."""
    try:
        api.health_check()
    except Exception:
        console.print("[bold yellow]⚠ Uvero service unavailable.[/bold yellow]")


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
):
    """Send content to the Uvero clipboard."""
    _check_health()

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

    try:
        result = api.send_clipboard(content)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    handle_api_error(result)

    code = result.get("data", {}).get("code", "")
    console.print(f"\n📋 [bold]Clipboard Code:[/bold] {code}")
    console.print(f"🔗 [link]https://uvero.app/{code}[/link]")


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
    _check_health()

    try:
        result = api.get_clipboard(code)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

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


if __name__ == "__main__":
    app()
