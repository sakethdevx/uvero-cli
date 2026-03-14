"""Board-related CLI commands (create / send / get)."""

from __future__ import annotations

import getpass
import sys
from typing import Any, Callable, Dict, Optional

import typer

from uvero import api
from uvero.utils import console, handle_api_error, is_piped, read_file, read_stdin

board_app = typer.Typer(
    help="Manage private shared boards.",
    epilog=(
        "Examples:\n"
        "  uvero board create\n"
        "  uvero board send abcd-def notes.txt\n"
        "  uvero board send abcd-def\n"
        "  uvero board get abcd-def"
    ),
)


def _call_api(
    api_function: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any
) -> Dict[str, Any]:
    """Run a backend call and map connection failures to a clean CLI message."""
    try:
        return api_function(*args, **kwargs)
    except api.UveroServiceConnectionError as exc:
        console.print("[bold red]❌ Cannot reach Uvero service[/bold red]")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]❌ Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


@board_app.command("create")
def board_create() -> None:
    """Create a new private board."""
    result = _call_api(api.create_board)

    handle_api_error(result)
    board_id = result.get("data", {}).get("board") or result.get("data", {}).get("id", "")
    console.print(f"[bold green]Board created:[/bold green] {board_id}")


@board_app.command("send")
def board_send(
    board: str = typer.Argument(..., help="Board identifier"),
    file: Optional[str] = typer.Argument(
        None,
        help="File to upload. Omit for interactive paste or pipe stdin.",
    ),
) -> None:
    """Send content to a board."""
    if file:
        try:
            content = read_file(file)
        except OSError as exc:
            console.print(f"[bold red]❌ Error:[/bold red] {exc}")
            raise typer.Exit(1) from exc
    elif is_piped():
        content = read_stdin()
    else:
        console.print("[dim]Paste your text below. Press CTRL+D when done.[/dim]")
        try:
            content = sys.stdin.read()
        except EOFError:
            content = ""

    result = _call_api(api.send_board, board, content)

    handle_api_error(result)
    console.print(f"[bold green]✔ Sent to board:[/bold green] {board}")


@board_app.command("get")
def board_get(
    board: str = typer.Argument(..., help="Board identifier"),
) -> None:
    """Retrieve content from a board."""
    result = _call_api(api.get_board, board)

    # Handle password-protected boards
    if result.get("requiresPassword"):
        password = getpass.getpass("Board password: ")
        result = _call_api(api.get_board, board, password=password)

    handle_api_error(result)
    content = result.get("data", {}).get("content", "")
    console.print(content)
