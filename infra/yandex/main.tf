terraform {
  required_version = ">= 1.5"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "~> 0.221"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# Auth (cloud_id + token, or a service account key file) comes from the
# standard YC_TOKEN / YC_CLOUD_ID env vars (or `yc` CLI's own config) —
# deliberately not put in a .tf file or tfvars alongside it.
provider "yandex" {
  zone      = var.zone
  folder_id = var.folder_id
}

# Bundles the shared script plus requirements.txt (boto3 — Yandex's
# Python runtime doesn't ship it) at the zip root. Yandex runs
# `pip install -r requirements.txt` at deploy time when it's present.
data "archive_file" "function" {
  type        = "zip"
  output_path = "${path.module}/build/function.zip"

  source {
    content  = file("${path.module}/../../function/now_playing.py")
    filename = "now_playing.py"
  }

  source {
    content  = file("${path.module}/../../function/requirements.txt")
    filename = "requirements.txt"
  }
}

# --- Object Storage: bucket + a dedicated SA with write access ---

resource "yandex_iam_service_account" "storage" {
  folder_id = var.folder_id
  name      = "${var.function_name}-storage"
}

resource "yandex_resourcemanager_folder_iam_member" "storage_editor" {
  folder_id = var.folder_id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.storage.id}"
}

resource "yandex_iam_service_account_static_access_key" "storage_key" {
  service_account_id = yandex_iam_service_account.storage.id
  description         = "static access key for now-playing.json writes"
}

# Only created (and its public-read policy only managed) when
# create_bucket is true -- an existing bucket's write access still
# works below via the service account's storage.editor role, which
# isn't scoped to a bucket Terraform has to own.
resource "yandex_storage_bucket" "now_playing" {
  count      = var.create_bucket ? 1 : 0
  bucket     = var.bucket_name
  access_key = yandex_iam_service_account_static_access_key.storage_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.storage_key.secret_key

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadNowPlaying"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::${var.bucket_name}/${var.output_key}"
    }]
  })
}

# --- Cloud Function + timer trigger ---

resource "yandex_iam_service_account" "function_exec" {
  folder_id = var.folder_id
  name      = "${var.function_name}-exec"
}

resource "yandex_resourcemanager_folder_iam_member" "function_invoker" {
  folder_id = var.folder_id
  role      = "functions.functionInvoker"
  member    = "serviceAccount:${yandex_iam_service_account.function_exec.id}"
}

resource "yandex_function" "now_playing" {
  name               = var.function_name
  runtime            = "python312"
  entrypoint         = "now_playing.yandex_handler"
  memory             = "128"
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.function_exec.id

  # Re-deploys a new version whenever the zip's contents change —
  # this hash already changes on any code change, so it doubles as
  # the "user_hash" Yandex requires to detect an update.
  user_hash = data.archive_file.function.output_base64sha256

  content {
    zip_filename = data.archive_file.function.output_path
  }

  # NOTE: same caveat as the AWS side — Terraform state isn't
  # encrypted by default, so these values (Spotify secrets, storage
  # static key) live in plaintext in local/remote state.
  environment = {
    OUTPUT_BUCKET         = var.bucket_name
    OUTPUT_KEY            = var.output_key
    SPOTIFY_CLIENT_ID     = var.spotify_client_id
    SPOTIFY_CLIENT_SECRET = var.spotify_client_secret
    SPOTIFY_REFRESH_TOKEN = var.spotify_refresh_token
    AWS_ACCESS_KEY_ID     = yandex_iam_service_account_static_access_key.storage_key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.storage_key.secret_key
  }
}

# 1-minute floor is a hard limit of Yandex's cron-based timer trigger —
# no native sub-minute schedules. See README.md's Terraform section.
resource "yandex_function_trigger" "poll" {
  name = "${var.function_name}-poll"

  timer {
    cron_expression = "* * * * ? *"
  }

  function {
    id                  = yandex_function.now_playing.id
    service_account_id = yandex_iam_service_account.function_exec.id
  }
}
