# uvero-cli

**Uvero** is an online clipboard service. This CLI lets you interact with it directly from your terminal.

## Installation

```bash
pip install uvero
```

## Usage

### Send content

```bash
# Interactive paste mode (CTRL+D to finish)
uv send

# Send a file
uv send notes.txt

# Send system clipboard contents
uv send -

# Pipe data
cat log.txt | uv send
```

### Retrieve content

```bash
# Save to uvero_4832.txt
uv get 4832

# Save to a specific file
uv get 4832 notes.txt

# Copy directly to system clipboard
uv get 4832 -c
```

### Boards (private shared clipboards)

```bash
# Create a board
uv board create

# Send to a board
uv board send abcd-def notes.txt
uv board send abcd-def   # interactive paste mode

# Get board content
uv board get abcd-def
```

## Help

```bash
uv --help
uv send --help
uv get --help
uv board --help
```