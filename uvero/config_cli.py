"""Configuration commands for Uvero CLI."""

import typer
from rich.table import Table

from uvero.config import EXIT_VALIDATION_ERR, state
from uvero.utils import console, print_json_output, print_message

config_app = typer.Typer(
    name="config",
    help="Manage global default settings for the Uvero CLI.",
    no_args_is_help=True,
)


@config_app.command("set")
def set_config(key: str, value: str):
    """Set a configuration value (e.g., output_mode json)."""
    valid_keys = {"output_mode", "auto_open", "clipboard_behavior", "quiet", "no_color", "no_emoji"}
    if key not in valid_keys:
        msg = f"Invalid config key '{key}'. Valid keys: {', '.join(valid_keys)}"
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR)

    # Cast boolean strings correctly
    if value.lower() in ("true", "1", "yes"):
        parsed_value = True
    elif value.lower() in ("false", "0", "no"):
        parsed_value = False
    else:
        parsed_value = value

    state.set_config(key, parsed_value)
    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "key": key, "value": parsed_value})
    else:
        print_message(f"Config '{key}' set to '{parsed_value}'", emoji="✔")


@config_app.command("get")
def get_config(key: str):
    """Get a configuration value."""
    if key not in state.config:
        msg = f"Config key '{key}' is not set."
        if state.get_config("output_mode") == "json":
            print_json_output({"success": False, "error": msg})
        else:
            print_message(msg, is_error=True, emoji="❌")
        raise typer.Exit(EXIT_VALIDATION_ERR)

    value = state.config[key]
    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "key": key, "value": value})
    else:
        print_message(str(value))


@config_app.command("list")
def list_config():
    """List all user-defined configuration values."""
    if state.get_config("output_mode") == "json":
        print_json_output({"success": True, "config": state.config})
        return

    if not state.config:
        print_message("No configuration values set. (Defaults are active)")
        return

    table = Table(title="Uvero CLI Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    for k, v in state.config.items():
        table.add_row(k, str(v))

    console.print(table)
