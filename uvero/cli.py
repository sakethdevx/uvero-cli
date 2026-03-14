"""Main CLI entry point for the `uvero` command."""

from __future__ import annotations

import re
import webbrowser
from importlib import metadata
from typing import Optional

import typer

from uvero import api
from uvero.boards import board_app
from uvero.clipboard import write_clipboard
from uvero.utils import (
    UveroCliUsageError,
    abort,
    call_api,
    console,
    deliver_text,
    install_update,
    notify_if_update_available,
    read_text_source,
    render_summary,
    resolve_text_target,
)

CODE_PATTERN = re.compile(r"^[0-9]{4}$")

app = typer.Typer(
    name="uvero",
    help=(
        "Share text through the Uvero online clipboard.\n\n"
        "Use `uvero send` to paste text, `uvero send clipboard` to share your local clipboard, "
        "or `uvero send file notes.txt` to upload a file. Use `uvero get CODE` to save content "
        "to a file, or `uvero get CODE clipboard` to copy it directly to your clipboard. "
        "Use `uvero open [CODE]` to open Uvero in your browser.\n\n"
        "Use `uvero board` for private shared boards."
    ),
    epilog=(
        "Examples:\n"
        "  uvero send\n"
        "  uvero send clipboard\n"
        "  uvero send file notes.txt\n"
        "  uvero send notes.txt\n"
        "  uvero send notes.txt --raw\n"
        "  uvero send paste\n"
        "  cat notes.txt | uvero send\n"
        "  uvero get 1234\n"
        "  uvero get 1234 clipboard\n"
        "  uvero get 1234 file notes.txt\n"
        "  uvero get 1234 notes.txt\n"
        "  uvero health\n"
        "  uvero open\n"
        "  uvero open 1234\n"
        "  uvero update\n"
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
    _ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed Uvero CLI version and exit.",
        is_eager=True,
    ),
) -> None:
    """Handle eager top-level options before dispatching commands."""
    if version:
        console.print(f"Uvero CLI v{_installed_version()}")
        raise typer.Exit()


def _validate_code(code: str) -> None:
    """Validate that *code* uses the expected 4-digit format."""
    if not CODE_PATTERN.fullmatch(code):
        abort("Clipboard code must be a 4 digit number.")


def _public_clipboard_url(code: str) -> str:
    """Return the public share URL for the clipboard *code*."""
    return f"{api.BASE_URL}/c/{code}"


@app.command(
    help="Send text to Uvero from interactive paste, your clipboard, stdin, or a file.",
    epilog=(
        "Examples:\n"
        "  uvero send\n"
        "  uvero send clipboard\n"
        "  uvero send file notes.txt\n"
        "  uvero send notes.txt\n"
        "  uvero send paste\n"
        "  cat notes.txt | uvero send"
    ),
)
def send(
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
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Print only the clipboard code (useful for scripting).",
    ),
) -> None:
    """Send content to the Uvero clipboard."""
    notify_if_update_available()

    try:
        content = read_text_source(
            source,
            value,
            interactive_prompt=(
                "Paste or type your text below. Press CTRL+D (Linux/Mac) or "
                "CTRL+Z then Enter (Windows) when you are done."
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

    result = call_api(api.send_clipboard, content)

    code = str(result.get("data", {}).get("code", "")).strip()
    if not code:
        abort("Missing clipboard code in the response.")

    if raw:
        console.print(code)
        return

    clipboard_status = "Not copied"
    try:
        write_clipboard(code)
    except Exception as exc:
        clipboard_status = f"Could not copy code: {exc}"
    else:
        clipboard_status = "Copied to your clipboard"

    render_summary(
        "Shared",
        [
            ("Code", code),
            ("Code saved", clipboard_status),
            ("Link", _public_clipboard_url(code)),
            ("Next step", f"uvero get {code}"),
        ],
    )


@app.command(
    help="Retrieve text from Uvero and save it to a file, your clipboard, or the terminal.",
    epilog=(
        "Examples:\n"
        "  uvero get 1234\n"
        "  uvero get 1234 clipboard\n"
        "  uvero get 1234 file notes.txt\n"
        "  uvero get 1234 notes.txt\n"
        "  uvero get 1234 stdout"
    ),
)
def get(
    code: str = typer.Argument(..., metavar="CODE", help="Clipboard code to retrieve."),
    target: Optional[str] = typer.Argument(
        None,
        metavar="[clipboard|stdout|file|FILE]",
        help="Choose where the text should go. Omit to save as uvero_CODE.txt.",
    ),
    value: Optional[str] = typer.Argument(
        None,
        metavar="[VALUE]",
        help="When using `file`, provide the path here. A single path also works for compatibility.",
    ),
) -> None:
    """Retrieve content from the Uvero clipboard."""
    notify_if_update_available()
    _validate_code(code)

    try:
        mode, destination = resolve_text_target(
            target,
            value,
            default_mode="file",
            default_path=f"uvero_{code}.txt",
        )
    except UveroCliUsageError as exc:
        abort(str(exc))

    result = call_api(api.get_clipboard, code)
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
        "Retrieved",
        [
            ("Code", code),
            ("Saved to", delivered_to),
            ("Open link", _public_clipboard_url(code)),
        ],
    )


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
    notify_if_update_available()
    if code is not None:
        _validate_code(code)
        url = _public_clipboard_url(code)
    else:
        url = api.BASE_URL

    if not webbrowser.open(url):
        abort("Could not open your browser.")

    console.print(f"🔗 {url}")


@app.command(help="Check whether the Uvero service is reachable.")
def health() -> None:
    """Check service availability."""
    notify_if_update_available()
    call_api(api.health_check)
    render_summary(
        "Health",
        [
            ("Service", "Reachable"),
            ("Base URL", api.BASE_URL),
        ],
    )


@app.command(help="Install the latest published Uvero CLI version.")
def update() -> None:
    """Update the installed CLI package."""
    install_update()


@app.command(help="Show the installed Uvero CLI version.")
def version() -> None:
    """Print the installed Uvero CLI version."""
    console.print(f"Uvero CLI v{_installed_version()}")


if __name__ == "__main__":
    app()
