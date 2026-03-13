# uvero-cli

**Uvero** is an online clipboard service. This CLI lets you interact with it directly from your terminal.

## Installation

```bash
pip install uvero
```

## Quick start

Run the built-in help first if you want a command overview:

```bash
uvero --help
uvero send --help
uvero get --help
uvero board --help
```

## How the CLI works

- `uvero send` uploads content and gives you a share code.
- `uvero get CODE` retrieves content using that code.
- A single `-` is special:
  - `uvero send -` reads from your system clipboard.
  - `uvero get CODE -` writes to your system clipboard.

## Usage

### Send content

```bash
# Interactive paste mode (CTRL+D to finish)
uvero send

# Send a file
uvero send notes.txt

# Send system clipboard contents
uvero send -

# Pipe data
cat log.txt | uvero send
```

### Retrieve content

```bash
# Save to uvero_4832.txt
uvero get 4832

# Save to a specific file
uvero get 4832 notes.txt

# Copy directly to system clipboard
uvero get 4832 -
```

If you omit the output path, Uvero saves the content to `uvero_CODE.txt`.

## Auto-updates

- On startup, Uvero checks PyPI (max once every 24 hours) and auto-upgrades when a newer version is available.
- The updated version is used from the next command run.
- To disable auto-upgrade, set `UVERO_AUTO_UPGRADE=0`.

### Boards (private shared clipboards)

```bash
# Create a board
uvero board create

# Send to a board
uvero board send abcd-def notes.txt
uvero board send abcd-def   # interactive paste mode

# Get board content
uvero board get abcd-def
```

For detailed command help at any time, run `uvero --help` or `uvero <command> --help`.
