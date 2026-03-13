"""Main CLI entry point – exposes the `uv` command."""

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
    name="uv",
    help="Uvero – online clipboard from your terminal.",
    no_args_is_help=True,
)

app.add_typer(board_app, name="board")


def _check_health() -> None:
    """Silently verify that the Uvero service is reachable."""
    try:
        api.health_check()
    except Exception:
        console.print("[bold yellow]⚠ Uvero service unavailable.[/bold yellow]")


@app.command()
def send(
    file: Optional[str] = typer.Argument(
        None,
        help="File to send. Use '-' to send the system clipboard.",
    ),
):
    """Send content to the Uvero clipboard.

    \b
    uv send            – interactive paste mode (or piped stdin)
    uv send file.txt   – send a file
    uv send -          – send system clipboard contents
    """
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
    console.print(f"🔗 [link]https://uvero.com/{code}[/link]")


@app.command()
def get(
    code: str = typer.Argument(..., help="Clipboard code to retrieve"),
    output: Optional[str] = typer.Argument(
        None,
        help="File path to write content to. Omit to auto-generate (uvero_CODE.txt).",
    ),
    copy: bool = typer.Option(
        False,
        "-c",
        help="Copy retrieved content to system clipboard.",
    ),
):
    """Retrieve content from the Uvero clipboard.

    \b
    uv get 4832           – save to uvero_4832.txt
    uv get 4832 notes.txt – save to notes.txt
    uv get 4832 -c        – copy to system clipboard
    """
    _check_health()

    try:
        result = api.get_clipboard(code)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    handle_api_error(result)

    content = result.get("data", {}).get("content", "")

    if copy:
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
