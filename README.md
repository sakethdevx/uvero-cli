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
uvero get 4832 -c
```

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

## Help

```bash
uvero --help
uvero send --help
uvero get --help
uvero board --help
```