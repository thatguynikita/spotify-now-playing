"""Fetch Spotify's currently-playing track and return it as JSON over
HTTP, computed fresh on every request.

Deployed as the Yandex Cloud Function in infra/yandex/, invoked
directly via its public HTTP URL -- no storage step, so cost scales
with actual request volume instead of a fixed schedule. Output shape
matches README.md's Interface section exactly.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"


def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    credentials = f"{client_id}:{client_secret}"
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


def _fetch_currently_playing(access_token: str) -> dict:
    req = urllib.request.Request(
        NOW_PLAYING_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
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
        "url": item.get("external_urls", {}).get("spotify"),
    }


def get_now_playing(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Returns a dict matching README.md's Interface section. Never
    raises -- failures degrade to {"is_playing": False} and log to
    stderr."""
    try:
        access_token = _refresh_access_token(client_id, client_secret, refresh_token)
        return _fetch_currently_playing(access_token)
    except Exception as e:
        print(f"Error fetching now-playing: {e}", file=sys.stderr)
        return {"is_playing": False}


def yandex_handler(event, context):
    """Yandex Cloud Function HTTP entry point -- see README.md's
    response-contract link for the {statusCode, headers, body} shape
    Yandex expects back."""
    data = get_now_playing(
        os.environ["SPOTIFY_CLIENT_ID"],
        os.environ["SPOTIFY_CLIENT_SECRET"],
        os.environ["SPOTIFY_REFRESH_TOKEN"],
    )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            # Lets a browser fetch() this cross-origin directly, without
            # requiring an nginx reverse proxy for a same-origin path.
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(data),
    }
