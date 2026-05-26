#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "plexapi>=4.15.0",
# ]
# ///

import os
import sys
import json
import time
import argparse
import textwrap
from pathlib import Path
from typing import Optional
from plexapi.exceptions import Unauthorized
from plexapi.myplex import MyPlexAccount
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

AUTH_CACHE_FILE = Path.home() / '.plex.json'


def _load_auth_cache() -> dict | None:
    """Load auth cache from file, returns None if missing or invalid."""
    if not AUTH_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_CACHE_FILE.read_text())
        if data.get('version') != 1:
            return None
        return data
    except Exception:
        return None


def _save_auth_cache(token: str) -> None:
    """Save auth token to cache file."""
    AUTH_CACHE_FILE.write_text(json.dumps({
        'version': 1,
        'cached_at': int(time.time()),
        'token': token,
    }, indent=2))
    AUTH_CACHE_FILE.chmod(0o600)


def _get_token(username: str, password: str) -> str:
    """Return a cached auth token, fetching from plex.tv only when needed."""
    cache = _load_auth_cache()
    if cache and cache.get('token'):
        return cache['token']
    account = MyPlexAccount(username, password)
    token = account.authenticationToken
    _save_auth_cache(token)
    return token


CLI_EPILOG = """
Authentication:
  Set PLEX_USERNAME, PLEX_PASSWORD, and PLEX_URL (or pass via --username/--password/--url)

Examples:
  plex libraries                                        # List all library sections
  plex movies                                           # List all movies
  plex movies "The Matrix"                              # Movie detail view
  plex movies --unwatched --sort year --limit 20        # Unwatched movies sorted by year
  plex movies --library "4K Movies"                     # Movies from specific library
  plex shows                                            # List all TV shows
  plex shows --unwatched                                # Unwatched shows
  plex shows "Breaking Bad"                             # Show seasons for a series
  plex shows "Breaking Bad" --season 3                  # List episodes in season 3
  plex search "heist"                                   # Search across all content
  plex search "office" --type show                      # Search only TV shows
  plex playlists                                        # List all playlists
  plex playlists "Road Trip"                            # View playlist contents
  plex playlists "Road Trip" --create                   # Create new empty playlist
  plex playlists "Road Trip" --delete                   # Delete playlist
  plex playlists "Road Trip" --add 1234                 # Add item by ID (from search)
  plex playlists "Road Trip" --remove 1234              # Remove item by ID (from playlist view)
  plex set 1234 --watched                               # Mark item as watched (movie, show, season, episode)
  plex set 1234 --unwatched                             # Mark item as unwatched
  plex set 1234 --rating 8.5                            # Set user rating (0–10)
  plex set 1234 --title "The Matrix" --sort-title "Matrix, The"
  plex set 1234 --original-title "La Vita è Bella"      # Set foreign/original title
  plex set 1234 --watched --rating 9 --title "New Name" # Combine multiple changes
"""

SORT_MAP = {
    'title': 'titleSort',
    'year': 'year',
    'added': 'addedAt',
    'rating': 'rating',
}


def fmt_duration(ms: int) -> str:
    if not ms:
        return ''
    total_sec = ms // 1000
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    if h:
        return f'{h}h {m:02d}m'
    return f'{m}m'


def watched_flag(item) -> str:
    try:
        return 'watched' if item.isWatched else 'unwatched'
    except Exception:
        return ''


class PlexClient:
    """Plex client wrapping plexapi."""

    def __init__(self, server):
        self.server = server

    @classmethod
    def connect(
        cls,
        username: Optional[str] = None,
        password: Optional[str] = None,
        url: Optional[str] = None,
    ) -> 'PlexClient':
        if not (username and password and url):
            raise ValueError('PLEX_USERNAME, PLEX_PASSWORD, and PLEX_URL are required')
        token = _get_token(username, password)
        try:
            plex = PlexServer(url, token)
        except Unauthorized:
            # token is stale — clear cache and re-auth once
            AUTH_CACHE_FILE.unlink(missing_ok=True)
            token = _get_token(username, password)
            plex = PlexServer(url, token)
        return cls(plex)

    def _find_library(self, name: Optional[str], lib_type: Optional[str] = None):
        if name:
            return self.server.library.section(name)
        for section in self.server.library.sections():
            if lib_type is None or section.type == lib_type:
                return section
        raise ValueError(f'No library found (type={lib_type})')

    def list_libraries(self) -> list[dict]:
        results = []
        for section in self.server.library.sections():
            count = section.totalSize if hasattr(section, 'totalSize') else len(section.all())
            results.append({
                'name': section.title,
                'type': section.type,
                'count': count,
            })
        return results

    def list_movies(
        self,
        library: Optional[str] = None,
        unwatched: bool = False,
        sort: str = 'titleSort',
        limit: Optional[int] = None,
    ) -> list[dict]:
        section = self._find_library(library, 'movie')
        kwargs = {'sort': sort}
        if unwatched:
            kwargs['unwatched'] = True
        items = section.search(**kwargs)
        if limit:
            items = items[:limit]
        results = []
        for m in items:
            results.append({
                'title': m.title,
                'year': m.year or '',
                'rating': f'{m.rating:.1f}' if m.rating else '',
                'duration': fmt_duration(m.duration),
                'watched': watched_flag(m),
                'summary': m.summary or '',
            })
        return results

    def get_movie(self, title: str, library: Optional[str] = None) -> dict:
        section = self._find_library(library, 'movie')
        results = section.search(title=title)
        if not results:
            raise ValueError(f'Movie not found: {title!r}')
        for r in results:
            if r.title.lower() == title.lower():
                m = r
                break
        else:
            m = results[0]
        return {
            'title': m.title,
            'year': m.year or '',
            'rating': f'{m.rating:.1f}' if m.rating else '',
            'user_rating': f'{m.userRating / 2:.1f}' if m.userRating else '',
            'duration': fmt_duration(m.duration),
            'studio': m.studio or '',
            'watched': watched_flag(m),
            'genres': ', '.join(g.tag for g in m.genres) if m.genres else '',
            'directors': ', '.join(d.tag for d in m.directors) if m.directors else '',
            'cast': ', '.join(r.tag for r in m.roles[:5]) if m.roles else '',
            'summary': m.summary or '',
            'id': m.ratingKey,
        }

    def list_shows(
        self,
        library: Optional[str] = None,
        unwatched: bool = False,
        sort: str = 'titleSort',
        limit: Optional[int] = None,
    ) -> list[dict]:
        section = self._find_library(library, 'show')
        kwargs = {'sort': sort}
        if unwatched:
            kwargs['unwatched'] = True
        items = section.search(**kwargs)
        if limit:
            items = items[:limit]
        results = []
        for s in items:
            results.append({
                'title': s.title,
                'year': s.year or '',
                'seasons': s.childCount,
                'episodes': s.leafCount,
                'watched': watched_flag(s),
            })
        return results

    def get_show(self, title: str, library: Optional[str] = None):
        section = self._find_library(library, 'show')
        results = section.search(title=title)
        if not results:
            raise ValueError(f'Show not found: {title!r}')
        for r in results:
            if r.title.lower() == title.lower():
                return r
        return results[0]

    def list_seasons(self, show) -> list[dict]:
        results = []
        for season in show.seasons():
            results.append({
                'number': season.index,
                'title': season.title,
                'episodes': season.leafCount,
                'watched': watched_flag(season),
            })
        return results

    def list_episodes(self, show, season_num: int) -> list[dict]:
        season = show.season(season_num)
        results = []
        for ep in season.episodes():
            results.append({
                'number': ep.index,
                'title': ep.title,
                'duration': fmt_duration(ep.duration),
                'watched': watched_flag(ep),
                'air_date': str(ep.originallyAvailableAt.date()) if ep.originallyAvailableAt else '',
                'summary': ep.summary or '',
                'user_rating': f'{ep.userRating / 2:.1f}' if ep.userRating else '',
                'id': ep.ratingKey,
            })
        return results

    def list_playlists(self) -> list[dict]:
        results = []
        for pl in self.server.playlists():
            if pl.smart:
                continue
            try:
                count = pl.leafCount
            except Exception:
                count = len(pl.items())
            results.append({
                'title': pl.title,
                'count': count,
                'duration': fmt_duration(pl.duration) if pl.duration else '',
            })
        return results

    def get_playlist(self, title: str):
        for pl in self.server.playlists():
            if pl.title.lower() == title.lower() and not pl.smart:
                return pl
        raise ValueError(f'Playlist not found: {title!r}')

    def get_playlist_items(self, playlist) -> list[dict]:
        results = []
        for item in playlist.items():
            duration = fmt_duration(item.duration) if getattr(item, 'duration', None) else ''
            if item.type == 'episode':
                subtitle = f'{item.grandparentTitle} S{item.parentIndex:02d}E{item.index:02d}'
            elif item.type == 'movie':
                subtitle = str(getattr(item, 'year', '') or '')
            else:
                subtitle = ''
            results.append({
                'id': item.ratingKey,
                'type': item.type,
                'title': item.title,
                'subtitle': subtitle,
                'duration': duration,
            })
        return results

    def create_playlist(self, title: str):
        Playlist.create(self.server, title, items=[])

    def delete_playlist(self, title: str):
        pl = self.get_playlist(title)
        pl.delete()

    def playlist_add_item(self, playlist, rating_key: int):
        item = self.server.fetchItem(rating_key)
        playlist.addItems([item])
        return item

    def playlist_remove_item(self, playlist, rating_key: int):
        items = playlist.items()
        matches = [i for i in items if i.ratingKey == rating_key]
        if not matches:
            raise ValueError(f'Item with ID {rating_key} not found in playlist')
        playlist.removeItems(matches[:1])
        return matches[0]

    def set_item(
        self,
        rating_key: int,
        *,
        watched: Optional[bool] = None,
        rating: Optional[float] = None,
        title: Optional[str] = None,
        sort_title: Optional[str] = None,
        original_title: Optional[str] = None,
    ) -> dict:
        if rating is not None and not (0 <= rating <= 10):
            raise ValueError(f'Rating must be between 0 and 10, got {rating}')
        item = self.server.fetchItem(rating_key)
        changes = []

        if watched is not None:
            if watched:
                item.markWatched()
            else:
                item.markUnwatched()
            changes.append(('status', 'watched' if watched else 'unwatched'))

        if rating is not None:
            item.rate(rating)
            changes.append(('rating', str(rating)))

        edits = [
            (title, 'editTitle', 'title'),
            (sort_title, 'editSortTitle', 'sort title'),
            (original_title, 'editOriginalTitle', 'original title'),
        ]
        if any(v is not None for v, _, _ in edits):
            item.batchEdits()
            for value, method_name, label in edits:
                if value is not None:
                    getattr(item, method_name)(value)
                    changes.append((label, value))
            item.saveEdits()

        return {
            'title': item.title,
            'type': item.type,
            'id': rating_key,
            'changes': changes,
        }

    def search(self, query: str, media_type: Optional[str] = None) -> list[dict]:
        results = self.server.search(query, mediatype=media_type)
        items = []
        for r in results:
            if not hasattr(r, 'ratingKey'):
                continue
            item = {
                'id': r.ratingKey,
                'type': r.type,
                'title': r.title,
                'year': getattr(r, 'year', '') or '',
            }
            if r.type == 'episode':
                show = r.grandparentTitle
                season_ep = f'S{r.parentIndex:02d}E{r.index:02d}' if r.parentIndex and r.index else ''
                item['subtitle'] = f'{show} — {season_ep}'
            elif r.type == 'season':
                item['subtitle'] = f'{r.parentTitle} — {r.title}'
            else:
                item['subtitle'] = getattr(r, 'studio', '') or ''
            items.append(item)
        return items


# ── command handlers ──────────────────────────────────────────────────────────

def get_client(args) -> PlexClient:
    username = getattr(args, 'username', None) or os.environ.get('PLEX_USERNAME')
    password = getattr(args, 'password', None) or os.environ.get('PLEX_PASSWORD')
    url = getattr(args, 'url', None) or os.environ.get('PLEX_URL')
    return PlexClient.connect(username=username, password=password, url=url)


def cmd_libraries(args):
    client = get_client(args)
    libs = client.list_libraries()

    if not libs:
        print('No libraries found')
        return 0

    name_w = max(max(len(l['name']) for l in libs), len('NAME'))
    type_w = max(max(len(l['type']) for l in libs), len('TYPE'))
    count_w = max(max(len(str(l['count'])) for l in libs), len('ITEMS'))

    header = f"{'NAME':<{name_w}}  {'TYPE':<{type_w}}  {'ITEMS':>{count_w}}"
    print(header)
    print('-' * len(header))
    for l in libs:
        print(f"{l['name']:<{name_w}}  {l['type']:<{type_w}}  {str(l['count']):>{count_w}}")
    return 0


def cmd_movies(args):
    client = get_client(args)

    if args.title:
        # ── detail view ───────────────────────────────────────────────────────
        m = client.get_movie(args.title, library=args.library)

        print(f"{m['title']} ({m['year']})")
        print()
        fields = [
            ('Duration', m['duration']),
            ('Status',   m['watched']),
            ('Rating',   m['rating']),
            ('Stars',    m['user_rating']),
            ('Studio',   m['studio']),
            ('Genres',   m['genres']),
            ('Director', m['directors']),
            ('Cast',     m['cast']),
        ]
        label_w = max(len(f[0]) for f in fields)
        for label, value in fields:
            if value:
                print(f"  {label:<{label_w}}  {value}")
        if m['summary']:
            print()
            wrapped = textwrap.fill(m['summary'], width=92, initial_indent='  ', subsequent_indent='  ')
            print(wrapped)
        print()
        print(f"  ID: {m['id']}")
        return 0

    # ── list view ─────────────────────────────────────────────────────────────
    sort_key = SORT_MAP.get(args.sort, 'titleSort')
    movies = client.list_movies(
        library=args.library,
        unwatched=args.unwatched,
        sort=sort_key,
        limit=args.limit,
    )

    if not movies:
        print('No movies found')
        return 0

    title_w = max(max(len(m['title']) for m in movies), len('TITLE'))
    year_w = max(max(len(str(m['year'])) for m in movies), len('YEAR'))
    rating_w = max(max(len(m['rating']) for m in movies), len('RATING'))
    dur_w = max(max(len(m['duration']) for m in movies), len('DURATION'))
    watch_w = max(max(len(m['watched']) for m in movies), len('STATUS'))

    header = (
        f"{'TITLE':<{title_w}}  {'YEAR':<{year_w}}  "
        f"{'RATING':>{rating_w}}  {'DURATION':>{dur_w}}  {'STATUS':<{watch_w}}"
    )
    indent = '  '
    sep_w = max(len(header), 2 + 90)
    print(header)
    print('-' * sep_w)
    for m in movies:
        print(
            f"{m['title']:<{title_w}}  {str(m['year']):<{year_w}}  "
            f"{m['rating']:>{rating_w}}  {m['duration']:>{dur_w}}  {m['watched']:<{watch_w}}"
        )
        if m['summary']:
            wrapped = textwrap.fill(m['summary'], width=2 + 90, initial_indent=indent, subsequent_indent=indent)
            print(wrapped)
        print()
    print(f'{len(movies)} movie(s)')
    return 0


def cmd_shows(args):
    client = get_client(args)

    if args.title and args.season is not None:
        # ── episode list ──────────────────────────────────────────────────────
        show = client.get_show(args.title, library=args.library)
        episodes = client.list_episodes(show, args.season)

        if not episodes:
            print(f'No episodes found in season {args.season}')
            return 0

        num_w = max(max(len(str(e['number'])) for e in episodes), len('#'))
        title_w = max(max(len(e['title']) for e in episodes), len('TITLE'))
        dur_w = max(max(len(e['duration']) for e in episodes), len('DURATION'))
        date_w = max(max(len(e['air_date']) for e in episodes), len('AIR DATE'))
        watch_w = max(max(len(e['watched']) for e in episodes), len('unwatched'))
        ur_w = max(max(len(e['user_rating']) for e in episodes), len('STARS'))

        print(f'{show.title} — Season {args.season}')
        print()
        header = (
            f"{'#':>{num_w}}  {'TITLE':<{title_w}}  "
            f"{'DURATION':>{dur_w}}  {'AIR DATE':<{date_w}}  {'STATUS':<{watch_w}}  {'STARS':>{ur_w}}"
        )
        indent = ' ' * (num_w + 2)
        sep_w = max(len(header), num_w + 2 + 90)
        print(header)
        print('-' * sep_w)
        for e in episodes:
            print(
                f"{str(e['number']):>{num_w}}  {e['title']:<{title_w}}  "
                f"{e['duration']:>{dur_w}}  {e['air_date']:<{date_w}}  {e['watched']:<{watch_w}}  {e['user_rating']:>{ur_w}}"
            )
            if e['summary']:
                wrapped = textwrap.fill(e['summary'], width=num_w + 2 + 90, initial_indent=indent, subsequent_indent=indent)
                print(wrapped)
            print(f'{indent}ID: {e["id"]}')
            print()
        print(f'{len(episodes)} episode(s)')

    elif args.title:
        # ── season list ───────────────────────────────────────────────────────
        show = client.get_show(args.title, library=args.library)
        seasons = client.list_seasons(show)

        if not seasons:
            print(f'No seasons found for {args.title!r}')
            return 0

        num_w = max(max(len(str(s['number'])) for s in seasons), len('#'))
        title_w = max(max(len(s['title']) for s in seasons), len('TITLE'))
        ep_w = max(max(len(str(s['episodes'])) for s in seasons), len('EPISODES'))
        watch_w = max(max(len(s['watched']) for s in seasons), len('STATUS'))

        print(f'{show.title} ({show.year})')
        print()
        header = f"{'#':>{num_w}}  {'TITLE':<{title_w}}  {'EPISODES':>{ep_w}}  {'STATUS':<{watch_w}}"
        print(header)
        print('-' * len(header))
        for s in seasons:
            print(
                f"{str(s['number']):>{num_w}}  {s['title']:<{title_w}}  "
                f"{str(s['episodes']):>{ep_w}}  {s['watched']:<{watch_w}}"
            )
        print(f'\n{len(seasons)} season(s)')

    else:
        # ── show list ─────────────────────────────────────────────────────────
        sort_key = SORT_MAP.get(args.sort, 'titleSort')
        shows = client.list_shows(
            library=args.library,
            unwatched=args.unwatched,
            sort=sort_key,
            limit=args.limit,
        )

        if not shows:
            print('No shows found')
            return 0

        title_w = max(max(len(s['title']) for s in shows), len('TITLE'))
        year_w = max(max(len(str(s['year'])) for s in shows), len('YEAR'))
        seasons_w = max(max(len(str(s['seasons'])) for s in shows), len('SEASONS'))
        ep_w = max(max(len(str(s['episodes'])) for s in shows), len('EPISODES'))
        watch_w = max(max(len(s['watched']) for s in shows), len('STATUS'))

        header = (
            f"{'TITLE':<{title_w}}  {'YEAR':<{year_w}}  "
            f"{'SEASONS':>{seasons_w}}  {'EPISODES':>{ep_w}}  {'STATUS':<{watch_w}}"
        )
        print(header)
        print('-' * len(header))
        for s in shows:
            print(
                f"{s['title']:<{title_w}}  {str(s['year']):<{year_w}}  "
                f"{str(s['seasons']):>{seasons_w}}  {str(s['episodes']):>{ep_w}}  {s['watched']:<{watch_w}}"
            )
        print(f'\n{len(shows)} show(s)')

    return 0


def cmd_search(args):
    client = get_client(args)
    results = client.search(args.query, media_type=args.type or None)

    if not results:
        print(f'No results for {args.query!r}')
        return 0

    id_w = max(max(len(str(r['id'])) for r in results), len('ID'))
    type_w = max(max(len(r['type']) for r in results), len('TYPE'))
    title_w = max(max(len(r['title']) for r in results), len('TITLE'))
    year_w = max(max(len(str(r['year'])) for r in results), len('YEAR'))
    sub_w = max(max(len(r['subtitle']) for r in results), len('INFO'))

    header = f"{'ID':>{id_w}}  {'TYPE':<{type_w}}  {'TITLE':<{title_w}}  {'YEAR':<{year_w}}  {'INFO':<{sub_w}}"
    print(header)
    print('-' * len(header))
    for r in results:
        print(
            f"{str(r['id']):>{id_w}}  {r['type']:<{type_w}}  {r['title']:<{title_w}}  "
            f"{str(r['year']):<{year_w}}  {r['subtitle']:<{sub_w}}"
        )
    print(f'\n{len(results)} result(s)')
    return 0


def cmd_playlists(args):
    if not args.title and (args.create or args.delete or args.add or args.remove):
        print('Error: a playlist title is required with --create, --delete, --add, and --remove', file=sys.stderr)
        return 1

    client = get_client(args)

    if args.title and args.create:
        client.create_playlist(args.title)
        print(f"Playlist created: '{args.title}'")
        return 0

    if args.title and args.delete:
        client.delete_playlist(args.title)
        print(f"Playlist deleted: '{args.title}'")
        return 0

    if args.title and args.add:
        playlist = client.get_playlist(args.title)
        item = client.playlist_add_item(playlist, args.add)
        if item.type == 'episode':
            label = f'{item.grandparentTitle} S{item.parentIndex:02d}E{item.index:02d} — {item.title}'
        else:
            label = item.title
        print(f"Added to '{args.title}': {label}")
        return 0

    if args.title and args.remove:
        playlist = client.get_playlist(args.title)
        item = client.playlist_remove_item(playlist, args.remove)
        print(f"Removed from '{args.title}': {item.title}")
        return 0

    if args.title:
        # ── view playlist contents ────────────────────────────────────────────
        playlist = client.get_playlist(args.title)
        items = client.get_playlist_items(playlist)
        if not items:
            print(f"'{args.title}' is empty")
            return 0

        id_w = max(max(len(str(i['id'])) for i in items), len('ID'))
        type_w = max(max(len(i['type']) for i in items), len('TYPE'))
        title_w = max(max(len(i['title']) for i in items), len('TITLE'))
        sub_w = max(max(len(i['subtitle']) for i in items), len('INFO'))
        dur_w = max(max(len(i['duration']) for i in items), len('DURATION'))

        print(f"{playlist.title} ({len(items)} item(s))")
        print()
        header = f"{'ID':>{id_w}}  {'TYPE':<{type_w}}  {'TITLE':<{title_w}}  {'INFO':<{sub_w}}  {'DURATION':>{dur_w}}"
        print(header)
        print('-' * len(header))
        for i in items:
            print(f"{str(i['id']):>{id_w}}  {i['type']:<{type_w}}  {i['title']:<{title_w}}  {i['subtitle']:<{sub_w}}  {i['duration']:>{dur_w}}")
        return 0

    # ── list all playlists ────────────────────────────────────────────────────
    playlists = client.list_playlists()

    if not playlists:
        print('No playlists found')
        return 0

    title_w = max(max(len(p['title']) for p in playlists), len('TITLE'))
    count_w = max(max(len(str(p['count'])) for p in playlists), len('ITEMS'))
    dur_w = max(max(len(p['duration']) for p in playlists), len('DURATION'))

    header = f"{'TITLE':<{title_w}}  {'ITEMS':>{count_w}}  {'DURATION':>{dur_w}}"
    print(header)
    print('-' * len(header))
    for p in playlists:
        print(f"{p['title']:<{title_w}}  {str(p['count']):>{count_w}}  {p['duration']:>{dur_w}}")
    print(f'\n{len(playlists)} playlist(s)')
    return 0


def cmd_set(args):
    opts = [args.watched, args.unwatched, args.rating, args.title, args.sort_title, args.original_title]
    if not any(o is not None and o is not False for o in opts):
        print('Error: specify at least one option to set (see plex set --help)', file=sys.stderr)
        return 1

    watched = True if args.watched else (False if args.unwatched else None)
    client = get_client(args)
    result = client.set_item(
        args.id,
        watched=watched,
        rating=args.rating,
        title=args.title,
        sort_title=args.sort_title,
        original_title=args.original_title,
    )

    if not result['changes']:
        print('No changes made')
        return 0

    print(f"{result['title']} ({result['type']}) — {len(result['changes'])} change(s)")
    label_w = max(len(c[0]) for c in result['changes'])
    for label, value in result['changes']:
        print(f"  {label:<{label_w}}  →  {value}")
    return 0


# ── argument parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='plex — explore Plex media server content',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CLI_EPILOG,
    )

    parser.add_argument('--username', help='Plex username/email (or PLEX_USERNAME)')
    parser.add_argument('--password', help='Plex password (or PLEX_PASSWORD)')
    parser.add_argument('--url', help='Plex server URL e.g. http://plex.local:32400 (or PLEX_URL)')

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # libraries
    lib_parser = subparsers.add_parser('libraries', help='List all library sections')
    lib_parser.set_defaults(func=cmd_libraries)

    # movies
    movies_parser = subparsers.add_parser('movies', help='List movies or view movie detail')
    movies_parser.add_argument('title', nargs='?', default=None, help='Movie title for detail view')
    movies_parser.add_argument('--library', '-l', help='Library section name')
    movies_parser.add_argument('--unwatched', action='store_true', help='Show only unwatched movies')
    movies_parser.add_argument('--sort', default='title', choices=['title', 'year', 'added', 'rating'], help='Sort order (default: title)')
    movies_parser.add_argument('--limit', '-n', type=int, help='Maximum number of results')
    movies_parser.set_defaults(func=cmd_movies)

    # shows
    shows_parser = subparsers.add_parser('shows', help='List shows, seasons, or episodes')
    shows_parser.add_argument('title', nargs='?', default=None, help='Show title; omit to list all shows')
    shows_parser.add_argument('--season', type=int, metavar='N', help='List episodes in season N (requires title)')
    shows_parser.add_argument('--library', '-l', help='Library section name')
    shows_parser.add_argument('--unwatched', action='store_true', help='Show only shows with unwatched episodes')
    shows_parser.add_argument('--sort', default='title', choices=['title', 'year', 'added'], help='Sort order (default: title)')
    shows_parser.add_argument('--limit', '-n', type=int, help='Maximum number of results')
    shows_parser.set_defaults(func=cmd_shows)

    # playlists
    playlists_parser = subparsers.add_parser('playlists', help='List playlists or view/manage a playlist')
    playlists_parser.add_argument('title', nargs='?', default=None, help='Playlist name; omit to list all playlists')
    pl_group = playlists_parser.add_mutually_exclusive_group()
    pl_group.add_argument('--create', action='store_true', help='Create this playlist (requires title)')
    pl_group.add_argument('--delete', action='store_true', help='Delete this playlist (requires title)')
    pl_group.add_argument('--add', metavar='ID', type=int, help='Add item by ID (requires title)')
    pl_group.add_argument('--remove', metavar='ID', type=int, help='Remove item by ID (requires title)')
    playlists_parser.set_defaults(func=cmd_playlists)

    # set
    set_parser = subparsers.add_parser('set', help='Set attributes on a media item by ID')
    set_parser.add_argument('id', type=int, help='Item ID (from search or detail views)')
    watch_group = set_parser.add_mutually_exclusive_group()
    watch_group.add_argument('--watched', action='store_true', default=None, help='Mark as watched')
    watch_group.add_argument('--unwatched', action='store_true', default=None, help='Mark as unwatched')
    set_parser.add_argument('--rating', type=float, metavar='N', help='User rating 0–10')
    set_parser.add_argument('--title', metavar='TEXT', help='Title')
    set_parser.add_argument('--sort-title', metavar='TEXT', dest='sort_title', help='Sort title (e.g. "Matrix, The")')
    set_parser.add_argument('--original-title', metavar='TEXT', dest='original_title', help='Original/foreign language title')
    set_parser.set_defaults(func=cmd_set)

    # search
    search_parser = subparsers.add_parser('search', help='Search for content')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--type', choices=['movie', 'show', 'episode'], help='Filter by media type')
    search_parser.set_defaults(func=cmd_search)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
