# plex.py

A Python CLI for browsing and managing a Plex media server.

## Features

- **Single-file executable** - Uses `uv run --script` with inline dependencies (PEP 723)
- **Library browsing** - List and filter movies, TV shows, seasons, and episodes
- **Search** - Full-text search across all media with type filtering
- **Playlists** - View, create, delete, and manage playlist contents
- **Watch status** - Filter by watched/unwatched, sort by rating, year, or date added
- **Environment variables** - Set credentials via `PLEX_USERNAME`, `PLEX_PASSWORD`, `PLEX_URL`
- **Auth token cache** - Token cached to `~/.plex.json` after first login; plex.tv is not hit on subsequent calls
- **Direct connection** - Connects directly to `PLEX_URL`, no plex.direct DNS or MyPlex resource lookup

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- A Plex account with at least one managed server

## Installation

```bash
# Clone and make executable
git clone https://github.com/vicgarcia/plex.py.git
cd plex.py
chmod +x plex.py

# Run
./plex.py --help

# Install
cp plex.py ~/.local/bin
chmod +x ~/.local/bin/plex.py
```

## Configuration

```bash
export PLEX_USERNAME="your@email.com"
export PLEX_PASSWORD="yourpassword"
export PLEX_URL="http://plex.yourdomain.com:32400"
```

Or pass as arguments: `plex.py --username user --password pass --url http://plex.local:32400 <command>`

Auth tokens are cached at `~/.plex.json` after first login. If a cached token fails, the tool retries with a fresh login automatically — no manual intervention needed.

## Commands

| Command | Description |
|---------|-------------|
| `libraries` | List all library sections |
| `movies [title]` | List movies or view movie detail |
| `shows [title]` | List shows, seasons, or episodes |
| `search query` | Search for content |
| `playlists [title]` | List or manage playlists |
| `set ID` | Set attributes on any media item by ID |

## Usage

### Libraries

```bash
plex.py libraries
```

### Movies

```bash
# List all movies
plex.py movies

# Filter and sort
plex.py movies --unwatched --sort rating --limit 10
plex.py movies --library "4K Movies"

# Detail view
plex.py movies "The Matrix"
```

### Shows

```bash
# List all shows
plex.py shows

# Browse a show
plex.py shows "Breaking Bad"           # seasons
plex.py shows "Breaking Bad" --season 3  # episodes
```

### Search

```bash
plex.py search "heist"
plex.py search "office" --type show
plex.py search "inception" --type movie
```

The ID column in search results is the `ratingKey` — use it with `playlists --add` to add items to playlists, or with `set` to update attributes.

### Playlists

```bash
# List all playlists
plex.py playlists

# View playlist contents
plex.py playlists "Road Trip"

# Create / delete
plex.py playlists "Road Trip" --create
plex.py playlists "Road Trip" --delete

# Add / remove items by ID
plex.py playlists "Road Trip" --add 1234
plex.py playlists "Road Trip" --remove 1234
```

## Command Options

### movies / shows

| Option | Description |
|--------|-------------|
| `--library` | Library section name |
| `--unwatched` | Show only unwatched content |
| `--sort` | `title` (default), `year`, `added`, `rating` |
| `--limit`, `-n` | Maximum results |

### shows (additional)

| Option | Description |
|--------|-------------|
| `--season N` | List episodes in season N |

### search

| Option | Description |
|--------|-------------|
| `--type` | Filter: `movie`, `show`, or `episode` |

### playlists (mutually exclusive flags)

| Flag | Description |
|------|-------------|
| `--create` | Create a new empty playlist |
| `--delete` | Delete the playlist |
| `--add ID` | Add item by ratingKey |
| `--remove ID` | Remove item by ratingKey |

### set

```bash
# Toggle watched status
plex.py set 1234 --watched
plex.py set 1234 --unwatched

# Set user rating (0–10)
plex.py set 1234 --rating 8.5

# Edit title fields
plex.py set 1234 --title "The Matrix" --sort-title "Matrix, The"
plex.py set 1234 --original-title "La Vita è Bella"

# Combine multiple changes in one call
plex.py set 1234 --watched --rating 9 --title "New Name"
```

Works for any item type — movies, shows, seasons, and episodes. Get the ID from `search`, a detail view, or an episode list.

| Option | Description |
|--------|-------------|
| `ID` | Item ratingKey (required) |
| `--watched` / `--unwatched` | Mark watched status (mutually exclusive) |
| `--rating N` | User rating, 0–10 |
| `--title TEXT` | Title |
| `--sort-title TEXT` | Sort title (e.g. `"Matrix, The"`) |
| `--original-title TEXT` | Original/foreign language title |

## Agent Skill

This project includes a `SKILL.md` file for use with AI coding agents (Claude Code, etc.). The skill enables natural language browsing and management of your Plex library.

### Installation

```bash
# Create skills directory
mkdir -p /path/to/agent/skills

# Copy SKILL.md
cp /path/to/plex.py/SKILL.md /path/to/agent/skills/plex/SKILL.md

# Ensure plex.py is executable and in PATH
chmod +x ~/.local/bin/plex.py

# Set credentials (in bashrc, zshrc, ...)
export PLEX_USERNAME="you@example.com"
export PLEX_PASSWORD="yourpass"
export PLEX_SERVER="My Server"
```

### Usage with Claude Code

Add the skills directory to your agent configuration, then interact naturally:

> "What movies do I have that I haven't watched yet?"
> "Show me the episodes in season 2 of The Sopranos"
> "Search for heist movies and add the best ones to my Movie Night playlist"
> "Create a playlist called Weekend and add Inception to it"

The agent reads `SKILL.md` to understand available commands, output formats, and how to use IDs to compose multi-step operations.
