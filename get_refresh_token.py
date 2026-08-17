#!/usr/bin/env python3
"""
One-time script to obtain a Spotify refresh token.

Shared by every deployment target (Yandex Cloud Function, VPS) -- run
once, then use the token in terraform.tfvars or the VPS env file. See
README.md's "Getting started".

Usage:
  1. Create an app at https://developer.spotify.com/dashboard
  2. Add "http://127.0.0.1:8888/callback" as a Redirect URI in the app settings
  3. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars
  4. Run: python3 get_refresh_token.py
  5. Open the printed URL, log in, approve access
  6. The refresh token will be printed in your terminal
"""

import base64
import http.server
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-currently-playing user-read-playback-state"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

auth_code = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Success! You can close this tab.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Something went wrong. Check the terminal.</h1>")

    def log_message(self, format, *args):
        pass  # silence default logging


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars first.", file=sys.stderr)
        sys.exit(1)

    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    })
    auth_url = f"{AUTH_URL}?{params}"

    print(f"Open this URL in a browser (any device) to authorize:\n\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server = http.server.HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    print("Waiting for authorization...")
    while auth_code is None:
        server.handle_request()

    print("Got authorization code, exchanging for tokens...")

    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_header = base64.b64encode(credentials.encode()).decode()

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }).encode()

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

    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        print(f"No refresh token in response: {payload}", file=sys.stderr)
        sys.exit(1)

    print("\n=== Your refresh token — save it for whichever deployment you're setting up ===\n")
    print(refresh_token)
    print()


if __name__ == "__main__":
    main()
