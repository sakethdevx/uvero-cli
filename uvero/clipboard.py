"""System clipboard helpers (read / write) using pyperclip."""

import pyperclip


def read_clipboard() -> str:
    """Return the current system clipboard content."""
    return str(pyperclip.paste())


def write_clipboard(text: str) -> None:
    """Write *text* to the system clipboard."""
    pyperclip.copy(text)
