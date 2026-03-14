"""Board-related CLI commands (create / send / get)."""

from __future__ import annotations

import getpass
from typing import Optional

import typer

from uvero import api
from uvero.utils import (
    UveroCliUsageError,
    abort,
    call_api,
    deliver_text,
    notify_if_update_available,
    read_text_source,
    render_summary,
    resolve_text_target,
)

board_app = typer.Typer(
    help="Manage private shared boards.",
    epilog=(
        "Examples:\n"
        "  uvero board create\n"
        "  uvero board create --ask-password\n"
        "  uvero board send abcd-def clipboard\n"
        "  uvero board send abcd-def file notes.txt\n"
        "  uvero board send abcd-def\n"
        "  uvero board get abcd-def\n"
        "  uvero board get abcd-def clipboard"
    ),
)

@board_app.command("create")
def board_create(
    password: Optional[str] = typer.Option(
        None,
        "--password",
        help="Protect the board with this password.",
        hide_input=True,
    ),
    ask_password: bool = typer.Option(
        False,
        "--ask-password",
        help="Prompt for a password when creating the board.",
    ),
) -> None:
    """Create a new private board."""
    notify_if_update_available()

    if password and ask_password:
        abort("Choose either `--password` or `--ask-password`, not both.")

    if ask_password:
        password = getpass.getpass("Board password: ")

    result = call_api(api.create_board, password=password)
    board_id = result.get("data", {}).get("board") or result.get("data", {}).get("id", "")
    if not board_id:
        abort("Missing board id in the response.")

    render_summary(
        "Board Created",
        [
            ("Board", board_id),
            ("Password", "Enabled" if password else "Not set"),
        ],
    )


@board_app.command("send")
def board_send(
    board: str = typer.Argument(..., help="Board identifier"),
    source: Optional[str] = typer.Argument(
        None,
        metavar="[clipboard|paste|stdin|file|FILE]",
        help="Choose where the text comes from. Omit to paste manually or use piped input.",
    ),
    value: Optional[str] = typer.Argument(
        None,
        metavar="[VALUE]",
        help="When using `file`, provide the path here. A single path also works for compatibility.",
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        help="Password for a protected board.",
        hide_input=True,
    ),
    ask_password: bool = typer.Option(
        False,
        "--ask-password",
        help="Prompt for a board password before sending.",
    ),
) -> None:
    """Send content to a board."""
    notify_if_update_available()

    if password and ask_password:
        abort("Choose either `--password` or `--ask-password`, not both.")

    if ask_password:
        password = getpass.getpass("Board password: ")

    try:
        content = read_text_source(
            source,
            value,
            interactive_prompt=(
                "Paste or type your board content below. Press CTRL+D (Linux/Mac) "
                "or CTRL+Z then Enter (Windows) when you are done."
            ),
        )
    except UveroCliUsageError as exc:
        abort(str(exc))
    except OSError as exc:
        abort(str(exc))
    except Exception as exc:
        if source and source.strip().lower() in {"clipboard", "-"}:
            abort(f"Could not read the clipboard: {exc}")
        abort(str(exc))

    if not content:
        abort("Nothing to send.")

    result = call_api(api.send_board, board, content, password=password)
    if result.get("requiresPassword") and not password:
        password = getpass.getpass("Board password: ")
        result = call_api(api.send_board, board, content, password=password)

    render_summary(
        "Board Updated",
        [
            ("Board", board),
            ("Content", "Sent successfully"),
            ("Password", "Used" if password else "Not required"),
        ],
    )


@board_app.command("get")
def board_get(
    board: str = typer.Argument(..., help="Board identifier"),
    target: Optional[str] = typer.Argument(
        None,
        metavar="[clipboard|stdout|file|FILE]",
        help="Choose where the board content should go. Omit to print it in the terminal.",
    ),
    value: Optional[str] = typer.Argument(
        None,
        metavar="[VALUE]",
        help="When using `file`, provide the path here. A single path also works for compatibility.",
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        help="Password for a protected board.",
        hide_input=True,
    ),
    ask_password: bool = typer.Option(
        False,
        "--ask-password",
        help="Prompt for a board password before retrieving content.",
    ),
) -> None:
    """Retrieve content from a board."""
    notify_if_update_available()

    if password and ask_password:
        abort("Choose either `--password` or `--ask-password`, not both.")

    if ask_password:
        password = getpass.getpass("Board password: ")

    try:
        mode, destination = resolve_text_target(
            target,
            value,
            default_mode="stdout",
        )
    except UveroCliUsageError as exc:
        abort(str(exc))

    result = call_api(api.get_board, board, password=password)

    if result.get("requiresPassword") and not password:
        password = getpass.getpass("Board password: ")
        result = call_api(api.get_board, board, password=password)

    content = result.get("data", {}).get("content", "")
    try:
        delivered_to = deliver_text(content, mode, destination)
    except UveroCliUsageError as exc:
        abort(str(exc))
    except OSError as exc:
        abort(str(exc))
    except Exception as exc:
        if mode == "clipboard":
            abort(f"Could not write to the clipboard: {exc}")
        abort(str(exc))

    if mode == "stdout":
        return

    render_summary(
        "Board Retrieved",
        [
            ("Board", board),
            ("Saved to", delivered_to),
        ],
    )
