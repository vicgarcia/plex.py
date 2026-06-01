---
name: plex
description: Browse and manage a Plex media server. Use when the user wants to explore their movie/TV library, search for content, check watch status, update metadata, or manage playlists. Covers libraries, movies, shows (seasons/episodes), search, playlist CRUD, and setting attributes (watched status, rating, titles) on any media item.
compatibility: Requires 'plex.py' script in PATH with PLEX_USERNAME, PLEX_PASSWORD, and PLEX_URL environment variables set.
---

# Plex Media Server Control

Browse and manage a Plex media server using the `plex.py` CLI.

## Important: Agent Behavior

**Always call `plex.py` sequentially — never in parallel.** Plex has rate limits that are not well-documented; concurrent requests will result in errors or throttling. Run one command, wait for it to complete, then run the next.

## Authentication

Credentials are loaded from environment variables:
```bash
export PLEX_USERNAME="your@email.com"
export PLEX_PASSWORD="yourpassword"
export PLEX_URL="http://plex.yourdomain.com:32400"
```

Or passed directly: `plex.py --username user --password pass --url http://plex.local:32400 <command>`

Auth tokens are cached at `~/.plex.json` after first login. Subsequent calls use the cached token — no plex.tv roundtrip. If the token is invalid, the cache is cleared and a fresh login is performed automatically.

## Commands Reference

### List Libraries
```bash
plex.py libraries
```
Returns all library sections with NAME, TYPE (movie/show/artist), and item count.
Use this to discover library names for use with `--library` on other commands.

### Movies
```bash
# List all movies
plex.py movies

# Filter and sort
plex.py movies --unwatched
plex.py movies --sort year --limit 20
plex.py movies --library "4K Movies"

# Detail view for a specific movie
plex.py movies "The Matrix"
```

**List output** — columns: TITLE, YEAR, RATING, DURATION, STATUS (watched/unwatched), summary excerpt

**Detail output** — Duration, Status, Rating, Stars (user rating), Studio, Genres, Director, Cast, summary, and **ID** (ratingKey). Use the ID to add the movie to a playlist.

**Movies options:**
| Option | Description |
|--------|-------------|
| `title` | Movie title for detail view; omit to list all |
| `--library` | Library section name (from `libraries`) |
| `--unwatched` | Show only unwatched movies |
| `--sort` | `title` (default), `year`, `added`, `rating` |
| `--limit`, `-n` | Maximum number of results |

### Shows
```bash
# List all shows
plex.py shows

# Filter and sort
plex.py shows --unwatched
plex.py shows --sort year --limit 10

# Show seasons for a series
plex.py shows "Breaking Bad"

# List episodes in a season
plex.py shows "Breaking Bad" --season 3
```

**Show list output** — columns: TITLE, YEAR, SEASONS, EPISODES, STATUS

**Season list output** — columns: #, TITLE, EPISODES, STATUS

**Episode list output** — columns: #, TITLE, DURATION, AIR DATE, STATUS, STARS, summary, and **ID** (ratingKey). Use the ID to add an episode to a playlist.

**Shows options:**
| Option | Description |
|--------|-------------|
| `title` | Show title; omit to list all shows |
| `--season N` | List episodes in season N (requires title) |
| `--library` | Library section name |
| `--unwatched` | Shows with unwatched episodes only |
| `--sort` | `title` (default), `year`, `added` |
| `--limit`, `-n` | Maximum number of results |

### Search
```bash
# Search across all content
plex.py search "heist"

# Filter by type
plex.py search "office" --type show
plex.py search "breaking" --type episode
plex.py search "inception" --type movie
```

**Output** — columns: ID, TYPE, TITLE, YEAR, INFO (studio or show/episode context)

The **ID** column is the `ratingKey` — use it with `plex.py playlists "Name" --add <ID>` to add items to playlists. Search is the primary way to find IDs without navigating to a detail view.

**Search options:**
| Option | Description |
|--------|-------------|
| `query` | Search term (required) |
| `--type` | `movie`, `show`, or `episode` |

### Playlists
```bash
# List all playlists
plex.py playlists

# View contents of a playlist
plex.py playlists "Road Trip"

# Create a new empty playlist
plex.py playlists "Road Trip" --create

# Delete a playlist
plex.py playlists "Road Trip" --delete

# Add an item by ID (from search or movie/episode detail)
plex.py playlists "Road Trip" --add 1234

# Remove an item by ID (from playlist view)
plex.py playlists "Road Trip" --remove 1234
```

**Playlist list output** — columns: TITLE, ITEMS, DURATION

**Playlist detail output** — columns: ID, TYPE, TITLE, INFO (year or S##E## show context), DURATION. The ID here can be passed to `--remove` to remove items.

**Playlists options:**
| Option | Description |
|--------|-------------|
| `title` | Playlist name; omit to list all |
| `--create` | Create a new empty playlist (requires title) |
| `--delete` | Delete the playlist (requires title) |
| `--add ID` | Add item by ratingKey (requires title) |
| `--remove ID` | Remove item by ratingKey (requires title) |

### Set
```bash
# Mark watched or unwatched
plex.py set 1234 --watched
plex.py set 1234 --unwatched

# Set user rating (0–10)
plex.py set 1234 --rating 8.5

# Edit title fields (locked against agent overwrite by default)
plex.py set 1234 --title "The Matrix"
plex.py set 1234 --sort-title "Matrix, The"
plex.py set 1234 --original-title "La Vita è Bella"

# Multiple changes in one call
plex.py set 1234 --watched --rating 9 --title "Corrected Title"
```

**Output** — item name, type, and a list of each changed field with its new value:
```
The Matrix (movie) — 2 change(s)
  status  →  watched
  rating  →  9.0
```

Works for any item type: movie, show, season, episode. The ID must be a `ratingKey` — get it from `search`, a movie/episode detail view, or `shows <title> --season N`.

**Set options:**
| Option | Description |
|--------|-------------|
| `ID` | Item ratingKey (required) |
| `--watched` / `--unwatched` | Mark watched status (mutually exclusive) |
| `--rating N` | User rating 0–10 |
| `--title TEXT` | Title |
| `--sort-title TEXT` | Sort title (e.g. `"Matrix, The"`) |
| `--original-title TEXT` | Original/foreign language title |

## Working with IDs

Plex items have a stable numeric ID (`ratingKey`). You need the ID to add/remove playlist items:

1. **From search:** `plex.py search "query"` — ID column in results
2. **From movie detail:** `plex.py movies "Title"` — ID printed at bottom
3. **From episode list:** `plex.py shows "Title" --season N` — ID printed per episode
4. **From playlist view:** `plex.py playlists "Name"` — ID column shows each item's ID

IDs are used with `playlists --add/--remove` and `set`.

## Example Workflows

**Build a movie night playlist:**
```bash
plex.py search "heist" --type movie          # find IDs
plex.py playlists "Movie Night" --create
plex.py playlists "Movie Night" --add 1234
plex.py playlists "Movie Night" --add 5678
plex.py playlists "Movie Night"              # verify contents
```

**Find something unwatched to watch:**
```bash
plex.py movies --unwatched --sort rating --limit 10
plex.py shows --unwatched --sort added --limit 10
```

**Check what's in a library:**
```bash
plex.py libraries                            # see all sections
plex.py movies --library "4K Movies"         # browse a specific section
```

**Browse a show:**
```bash
plex.py shows "The Wire"                     # see seasons
plex.py shows "The Wire" --season 1          # see episodes with IDs
```

**Mark a movie watched and rate it:**
```bash
plex.py search "inception" --type movie      # get ID
plex.py set 1234 --watched --rating 9
```

**Fix a title or sort order:**
```bash
plex.py search "matrix" --type movie         # get ID
plex.py set 1234 --sort-title "Matrix, The"
```
