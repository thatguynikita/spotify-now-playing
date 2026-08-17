#!/usr/bin/env python3
"""
Fetches the currently-playing Spotify track and writes it as JSON to
a static file. Secrets come from env vars, loaded from
/etc/spotify-widget.env by the systemd service.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    credentials = f"{client_id}:{client_secret}"
    import base64
    auth_header = base64.b64encode(credentials.encode()).decode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode())
        return payload["access_token"]


def fetch_now_playing(access_token: str) -> dict:
    req = urllib.request.Request(
        NOW_PLAYING_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
                # Nothing currently playing
                return {"is_playing": False}
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return {"is_playing": False}
        raise

    if not payload or not payload.get("item"):
        return {"is_playing": False}

    item = payload["item"]
    artists = ", ".join(a["name"] for a in item.get("artists", []))

    return {
        "is_playing": payload.get("is_playing", False),
        "track": item.get("name"),
        "artist": artists,
        "album": item.get("album", {}).get("name"),
        "url": item.get("external_urls", {}).get("spotify"),
    }


def write_output(data: dict, path: str) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    os.replace(tmp_path, path)  # atomic write, avoids partial reads


def main():
    client_id = get_env("SPOTIFY_CLIENT_ID")
    client_secret = get_env("SPOTIFY_CLIENT_SECRET")
    refresh_token = get_env("SPOTIFY_REFRESH_TOKEN")
    # No default -- deployment-specific; set in spotify-widget.env.
    output_path = get_env("OUTPUT_PATH")

    try:
        access_token = refresh_access_token(client_id, client_secret, refresh_token)
        now_playing = fetch_now_playing(access_token)
    except Exception as e:
        print(f"Error fetching now-playing: {e}", file=sys.stderr)
        # Fallback so the widget doesn't show stale data
        write_output({"is_playing": False}, output_path)
        sys.exit(1)

    write_output(now_playing, output_path)


if __name__ == "__main__":
    main()
