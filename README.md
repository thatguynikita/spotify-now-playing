# spotify-now-playing

A Spotify "now playing" widget backend — polls the Spotify API on a
schedule and writes one small `now-playing.json` file, either to an
S3-compatible bucket (Yandex Object Storage) or to a local file on a
VPS, that any frontend, script, app, or other consumer can poll to
show what's currently playing. Pick a deployment target (Yandex Cloud
Function, or a plain VPS + cron/nginx).

## Interface

**Something is playing:**
```json
{
  "is_playing": true,
  "track": "Song title",
  "artist": "Artist name, comma-separated if several",
  "url": "https://open.spotify.com/track/..."
}
```

**Nothing playing, or the widget can't reach Spotify:**
```json
{ "is_playing": false }
```

### Example consumer

[`now-playing-widget.html`](now-playing-widget.html)
is a real, working reference frontend — drop-in markup/CSS/JS to your website. It polls
`/now-playing.json` every 20 seconds with `fetch(url, { cache: 'no-store' })`:

- `is_playing: true` + a `track` → shows a scrolling `"♫ <track> — <artist>"`
  ticker.
- `is_playing: false`, or the fetch/parse fails outright → shows "Not
  listening to anything right now" and pauses the scroll animation
  (the same UI state either way — the file doesn't distinguish "idle"
  from "unreachable," though your own frontend is free to).

Adjust `ENDPOINT` in its `<script>` if you're not serving the JSON
from your site's root, and `POLL_MS` if you want a different polling
interval. Use it as-is, or as a template for your own frontend — the
JSON shape above is all it actually depends on.

## Deployment strategies

Two ways to run this, both producing the same JSON at whatever URL
you point your frontend at:

| | What it is | Runs on a schedule via |
|---|---|---|
| **Yandex Cloud Function** | `function/now_playing.py`'s `yandex_handler`, writing to Yandex Object Storage | a cron-based timer trigger |
| **Self-hosted VPS** | `infra/vps/spotify_now_playing.py`, writing a local file | a systemd timer |

The Yandex Cloud Function polls **every 1 minute** — a limitation of
its cron-based timer trigger (no native sub-minute schedules). The VPS
path isn't subject to that limit (its systemd timer can run as often
as you like) but defaults to the same cadence for consistency.

`infra/yandex/` is a self-contained Terraform root module; `infra/vps/`
is a plain systemd + nginx setup, not Terraform-managed.

## Getting started

### 1. Create a Spotify app
- Go to https://developer.spotify.com/dashboard → Create app
- Add Redirect URI: `http://127.0.0.1:8888/callback`
- Copy the **Client ID** and **Client Secret**

### 2. Get a refresh token
```bash
export SPOTIFY_CLIENT_ID=xxxx
export SPOTIFY_CLIENT_SECRET=xxxx
python3 get_refresh_token.py
```
Open the printed URL, approve access, copy the refresh token that gets
printed. Run this once, from anywhere with a browser — it isn't tied
to any of the deployment targets below.

You now have three values (client ID, client secret, refresh token)
that go into whichever deployment option you pick next.

## Choose your deployment

- **[Yandex Cloud Function](#yandex-cloud-function-deployment)** — Terraform, deploys a Cloud Function + Object Storage bucket + timer trigger.
- **[Self-hosted VPS](#self-hosted-vps-deployment)** — systemd timer + nginx, on a server you already run.

## Yandex Cloud Function deployment

Provisions one Cloud Function (running [`function/now_playing.py`](function/now_playing.py)'s
`yandex_handler`), one Object Storage bucket it writes
`now-playing.json` to, and a timer trigger that invokes it every
minute.

### Prerequisites

- A Spotify client ID, client secret, and refresh token — see
  ["Getting started"](#getting-started) above if you don't have these yet.
- A Yandex Cloud `folder_id` (goes in `terraform.tfvars`) and a `yc`
  CLI already authenticated against your account.
- Terraform >= 1.5.

### Deploy

```bash
cd infra/yandex
cp terraform.tfvars.example terraform.tfvars
# fill in terraform.tfvars: folder_id, bucket_name, spotify_client_id/secret/refresh_token

export YC_TOKEN=$(yc iam create-token)
terraform init
terraform plan
terraform apply
```

`terraform apply` prints a `now_playing_url` output — that's the
public Object Storage URL serving the output object. Point your
frontend (or an nginx `proxy_pass`) at that URL.

By default Terraform creates the bucket and writes to `now-playing.json`
at its root; set `create_bucket = false` to use a bucket you already
manage, and/or `output_key` to write to any other path in it — see
`terraform.tfvars.example`. Note: write access works either way via
the storage service account's `storage.editor` role, but Terraform can
only manage the bucket's public-read policy when it also creates the
bucket (the Yandex provider ties policy to bucket creation) — configure
public read yourself if bringing your own bucket.

### Secrets

Spotify credentials are Terraform variables marked `sensitive`,
supplied via `terraform.tfvars`.
Terraform state itself isn't encrypted by default, so those values —
plus the storage service account's static access key — end up in
plaintext in `terraform.tfstate`. Fine for a personal project with
local state; move to a remote backend with encryption at rest if that
ever changes.

## Self-hosted VPS deployment

A systemd-timer + VPS implementation, for anyone who'd rather
self-host on a server they already have than use a cloud function. The
commands and paths below use illustrative example values (domain,
paths, user); swap in your own throughout.

### Prerequisites

A Spotify client ID, client secret, and refresh token — see
["Getting started"](#getting-started) above if you don't have these yet.

### 1. Copy files to the VPS
```bash
# Output directory must exist and be writable by www-data *before* the
# service ever runs — create and chown it first.
sudo mkdir -p /var/www/your-domain-name
sudo chown www-data:www-data /var/www/your-domain-name

sudo mkdir -p /opt/spotify-widget
sudo cp infra/vps/spotify_now_playing.py /opt/spotify-widget/

sudo cp infra/vps/spotify-widget.env /etc/spotify-widget.env
sudo nano /etc/spotify-widget.env   # fill in client id/secret/refresh token, and OUTPUT_PATH
sudo chmod 600 /etc/spotify-widget.env
sudo chown root:root /etc/spotify-widget.env

sudo cp infra/vps/spotify-widget.service /etc/systemd/system/
sudo nano /etc/systemd/system/spotify-widget.service   # update ReadWritePaths to match OUTPUT_PATH's directory
sudo cp infra/vps/spotify-widget.timer /etc/systemd/system/
```

### 2. Enable and start the timer
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spotify-widget.timer

# sanity check it ran
sudo systemctl start spotify-widget.service
cat /var/www/your-domain-name/now-playing.json   # adjust path to your own OUTPUT_PATH
```

### 3. Add a location block to nginx to serve the JSON file

Add this inside your existing HTTPS server block for the domain,
alongside your existing `location /`:

```nginx
location = /now-playing.json {
    alias /var/www/your-domain-name/now-playing.json;
    add_header Cache-Control "no-store";
    default_type application/json;
}
```

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

Then verify:
```bash
curl https://your-domain/now-playing.json
```

### 4. Frontend integration

Once steps 1–3 are done, any frontend polling `/now-playing.json` picks
the widget up automatically — see ["Example consumer"](#example-consumer).