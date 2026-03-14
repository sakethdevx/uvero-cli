# Uvero CLI v0.2.0

## Changes
This release concludes the Phase 1, Phase 2, and Phase 3 improvements to the Uvero CLI:

* **Machine Output & UX Controls**: Added global `--json`, `--quiet`, `--no-color`, and `--no-emoji` flags for scripting and enterprise accessibility. 
* **Diagnostics & Updates**: Added `uvero doctor` for environment health checks and `uvero update` to manually trigger PyPI upgrades.
* **Persistent Configuration**: New `uvero config [get|set|list]` command backed by `~/.uvero/config.json` state management.
* **CLI Refinements**: `uvero send` now supports `--open` and `--copy-link`. `uvero get` introduces the explicit `--stdout` flag.
* **Engineering Quality**: Full `pytest` integration replacing mocked endpoints, strict `mypy` type validation, `ruff` format/lint bindings, standard explicit exception exit codes, and exhaustive CI validation matrices from Python 3.8 to 3.12.

## Migration Notes
No specific migration steps required.
