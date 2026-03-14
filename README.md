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
uvero --version
uvero send --help
uvero get --help
uvero health
uvero open --help
uvero update
uvero version
uvero board --help
```

## How the CLI works

- `uvero send` lets you paste or type content, then uploads it and copies the code to your clipboard.
- Public share links use `https://uvero.app/c/CODE`.
- `uvero get CODE` retrieves content using that code.
- `uvero open [CODE]` opens Uvero in your browser (home page if code is omitted).
- `uvero health` checks whether the Uvero service is reachable.
- `uvero update` installs the newest published CLI version.
- Readable source and destination words are supported:
  - `clipboard` uses your local clipboard.
  - `file PATH` reads from or writes to a file.
  - `stdout` prints retrieved text in the terminal.
- Legacy `-` clipboard shortcuts still work, but `clipboard` is now the preferred form.

## Usage

### Send content

```bash
# Paste or type text, then finish with CTRL+D
uvero send

# Send local clipboard contents
uvero send clipboard

# Send a file
uvero send file notes.txt

# A direct path still works
uvero send notes.txt

# Force interactive paste mode
uvero send paste

# Pipe data
cat log.txt | uvero send

# Print only the code (for scripting)
uvero send notes.txt --raw
```

### Retrieve content

```bash
# Save to uvero_4832.txt
uvero get 4832

# Copy directly to system clipboard
uvero get 4832 clipboard

# Print directly in the terminal
uvero get 4832 stdout

# Save to a specific file
uvero get 4832 file notes.txt

# Save to a specific file
uvero get 4832 notes.txt
```

If you omit the output path, Uvero saves the content to `uvero_CODE.txt`.

### Open a clipboard link in browser

```bash
# Open Uvero home page
uvero open

# Open clipboard page
uvero open 4832
```

### Check service health

```bash
uvero health
```

### Show CLI version

```bash
uvero --version
uvero version
```

## Updates

- On startup, Uvero checks PyPI at most once every 24 hours and shows a lightweight update notice when a newer version is available.
- To disable update checks, set `UVERO_UPDATE_CHECK=0` or `UVERO_AUTO_UPGRADE=0`.
- Install updates explicitly with:

```bash
uvero update
```

### Boards (private shared clipboards)

```bash
# Create a board
uvero board create

# Create a password-protected board
uvero board create --ask-password

# Send to a board
uvero board send abcd-def clipboard
uvero board send abcd-def file notes.txt
uvero board send abcd-def   # interactive paste mode

# Get board content
uvero board get abcd-def
uvero board get abcd-def clipboard
uvero board get abcd-def stdout --password your-password
```

For detailed command help at any time, run `uvero --help` or `uvero <command> --help`.
