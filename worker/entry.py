"""Cloudflare Worker entry point around function/now_playing.py
(symlinked here so wrangler bundles it). Same JSON and headers as the
Lambda/Yandex handler."""

from js import AbortSignal
from pyodide.ffi import run_sync
from workers import Response, WorkerEntrypoint, fetch

from now_playing import get_now_playing


def _fetch_request(url, method, headers, data, timeout):
    # urllib can't reach the network under Pyodide; bridge to the
    # runtime's fetch and block on it (JSPI) so the shared code stays sync.
    resp = run_sync(fetch(
        url,
        method=method,
        headers=headers,
        body=data,
        signal=AbortSignal.timeout(timeout * 1000),
    ))
    return resp.status, run_sync(resp.bytes())


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        data = get_now_playing(
            self.env.SPOTIFY_CLIENT_ID,
            self.env.SPOTIFY_CLIENT_SECRET,
            self.env.SPOTIFY_REFRESH_TOKEN,
            request=_fetch_request,
        )
        return Response.json(data, headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        })
