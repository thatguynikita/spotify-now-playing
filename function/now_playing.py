"""Fetch Spotify's currently-playing track and return it as JSON over
HTTP, computed fresh on every request.

Runs unmodified as either an AWS Lambda or a Yandex Cloud Function
(see README.md's deployment sections), invoked directly via its public
HTTP URL. The Cloudflare Worker in worker/ imports it too, swapping the
urllib transport for one built on the runtime's fetch. Output shape
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


def _urllib_request(url: str, method: str, headers: dict, data, timeout) -> tuple:
    """Default transport: (status, body). Non-2xx is returned, not raised."""
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _refresh_access_token(request, client_id: str, client_secret: str, refresh_token: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    credentials = f"{client_id}:{client_secret}"
    auth_header = base64.b64encode(credentials.encode()).decode()

    status, body = request(
        TOKEN_URL,
        "POST",
        {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data,
        10,
    )
    if status != 200:
        raise RuntimeError(f"token refresh returned HTTP {status}")
    return json.loads(body)["access_token"]


def _fetch_currently_playing(request, access_token: str) -> dict:
    status, body = request(
        NOW_PLAYING_URL,
        "GET",
        {"Authorization": f"Bearer {access_token}"},
        None,
        10,
    )
    if status == 204:
        return {"is_playing": False}
    if status != 200:
        raise RuntimeError(f"currently-playing returned HTTP {status}")

    payload = json.loads(body)
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


def get_now_playing(client_id: str, client_secret: str, refresh_token: str,
                    request=_urllib_request) -> dict:
    """Returns a dict matching README.md's Interface section. Never
    raises -- failures degrade to {"is_playing": False} and log to
    stderr. `request(url, method, headers, data, timeout)` must return
    (status, body); see _urllib_request."""
    try:
        access_token = _refresh_access_token(request, client_id, client_secret, refresh_token)
        return _fetch_currently_playing(request, access_token)
    except Exception as e:
        print(f"Error fetching now-playing: {e}", file=sys.stderr)
        return {"is_playing": False}


def handler(event, context):
    """HTTP entry point. AWS Lambda function URLs and Yandex Cloud
    Functions expect the same {statusCode, headers, body} response
    shape, so this handler works on both as-is."""
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
