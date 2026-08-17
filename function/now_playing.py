"""Fetch Spotify's currently-playing track and write it as JSON to
S3-compatible storage.

One file, two entry points — aws_handler for AWS Lambda,
yandex_handler for Yandex Cloud Functions — sharing all the
Spotify-fetching logic and differing only in which storage endpoint
boto3 talks to. Output shape matches README.md's Interface section
exactly.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import boto3

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
    """Returns a dict matching README.md's Interface section.

    Never raises — any failure talking to Spotify (network, auth, rate
    limit) degrades to {"is_playing": False}, the same "can't reach
    Spotify" state the contract already defines, logged to stderr for
    whichever platform's log stream is watching.
    """
    try:
        access_token = _refresh_access_token(client_id, client_secret, refresh_token)
        return _fetch_currently_playing(access_token)
    except Exception as e:
        print(f"Error fetching now-playing: {e}", file=sys.stderr)
        return {"is_playing": False}


def _run(**s3_client_kwargs) -> dict:
    data = get_now_playing(
        os.environ["SPOTIFY_CLIENT_ID"],
        os.environ["SPOTIFY_CLIENT_SECRET"],
        os.environ["SPOTIFY_REFRESH_TOKEN"],
    )

    s3 = boto3.client("s3", **s3_client_kwargs)
    s3.put_object(
        Bucket=os.environ["OUTPUT_BUCKET"],
        Key=os.environ.get("OUTPUT_KEY", "now-playing.json"),
        Body=json.dumps(data).encode(),
        ContentType="application/json",
        CacheControl="no-store",
    )

    return {"statusCode": 200}


def aws_handler(event, context):
    """AWS Lambda entry point — default boto3 S3 client (real AWS S3)."""
    return _run()


def yandex_handler(event, context):
    """Yandex Cloud Function entry point — boto3 pointed at Yandex's
    S3-compatible Object Storage endpoint. Credentials come from the
    standard AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars (see
    infra/yandex), populated from a Yandex static access key."""
    return _run(
        endpoint_url="https://storage.yandexcloud.net",
        region_name="ru-central1",
    )
