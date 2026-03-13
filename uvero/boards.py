"""Board-related CLI commands (create / send / get)."""

from __future__ import annotations

import getpass
import sys
from typing import Optional

import typer

from uvero import api
from uvero.utils import console, handle_api_error, is_piped, read_file, read_stdin

board_app = typer.Typer(help="Manage private boards.")


@board_app.command("create")
def board_create():
    """Create a new private board."""
    try:
        result = api.create_board()
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    handle_api_error(result)
    board_id = result.get("data", {}).get("board") or result.get("data", {}).get("id", "")
    console.print(f"[bold green]Board created:[/bold green] {board_id}")


@board_app.command("send")
def board_send(
    board: str = typer.Argument(..., help="Board identifier"),
    file: Optional[str] = typer.Argument(None, help="File to upload (omit for paste mode)"),
):
    """Send content to a board."""
    if file:
        try:
            content = read_file(file)
        except OSError as exc:
            console.print(f"[bold red]❌ Error:[/bold red] {exc}")
            raise typer.Exit(1)
    elif is_piped():
        content = read_stdin()
    else:
        console.print("[dim]Paste your text below. Press CTRL+D when done.[/dim]")
        try:
            content = sys.stdin.read()
        except EOFError:
            content = ""

    try:
        result = api.send_board(board, content)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    handle_api_error(result)
    console.print(f"[bold green]✔ Sent to board:[/bold green] {board}")


@board_app.command("get")
def board_get(
    board: str = typer.Argument(..., help="Board identifier"),
):
    """Retrieve content from a board."""
    try:
        result = api.get_board(board)
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1)

    # Handle password-protected boards
    if result.get("requiresPassword"):
        password = getpass.getpass("Board password: ")
        try:
            result = api.get_board(board, password=password)
        except Exception as exc:
            console.print(f"[bold red]❌ Error:[/bold red] {exc}")
            raise typer.Exit(1)

    handle_api_error(result)
    content = result.get("data", {}).get("content", "")
    console.print(content)
