"""Global state and configuration handling for Uvero CLI."""

import json
from pathlib import Path
from typing import Any, Dict

_CONFIG_DIR = Path.home() / ".uvero"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

# Exit Codes
EXIT_SUCCESS = 0
EXIT_NETWORK_ERR = 2
EXIT_API_ERR = 3
EXIT_VALIDATION_ERR = 4
EXIT_ENV_ERR = 5


class GlobalState:
    """Manages global CLI state and user-defined configuration defaults."""

    def __init__(self) -> None:
        self.config = self._load_config()
        self.json_output = False
        self.quiet = False
        self.no_color = False
        self.no_emoji = False

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from ~/.uvero/config.json."""
        try:
            return dict(json.loads(_CONFIG_FILE.read_text()))
        except Exception:
            return {}

    def save_config(self) -> None:
        """Save current configuration to disk."""
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _CONFIG_FILE.write_text(json.dumps(self.config, indent=4))
        except Exception:
            pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value, merging with global flags if applicable."""
        config_val = self.config.get(key, default)
        # Apply CLI flag overrides dynamically
        if key == "output_mode" and self.json_output:
            return "json"
        if key == "quiet" and self.quiet:
            return True
        if key == "no_color" and self.no_color:
            return True
        if key == "no_emoji" and self.no_emoji:
            return True
        return config_val

    def set_config(self, key: str, value: Any) -> None:
        """Set an persist a configuration value."""
        self.config[key] = value
        self.save_config()


state = GlobalState()
