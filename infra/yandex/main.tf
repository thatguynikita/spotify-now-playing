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

# Auth: export YC_TOKEN=$(yc iam create-token) before running Terraform
# (the provider does not read the yc CLI's own config automatically).
# folder_id comes from the folder_id variable below, not an env var.
provider "yandex" {
  zone      = var.zone
  folder_id = var.folder_id
}

# Pure stdlib -- no requirements.txt to bundle.
data "archive_file" "function" {
  type        = "zip"
  output_path = "${path.module}/build/function.zip"

  source {
    content  = file("${path.module}/../../function/now_playing.py")
    filename = "now_playing.py"
  }
}

resource "yandex_function" "now_playing" {
  name              = var.function_name
  runtime           = "python312"
  entrypoint        = "now_playing.yandex_handler"
  memory            = "128"
  execution_timeout = "10"

  # Changes whenever the zip changes -- satisfies Yandex's required user_hash.
  user_hash = data.archive_file.function.output_base64sha256

  content {
    zip_filename = data.archive_file.function.output_path
  }

  # Terraform state isn't encrypted by default -- these are plaintext in state.
  environment = {
    SPOTIFY_CLIENT_ID     = var.spotify_client_id
    SPOTIFY_CLIENT_SECRET = var.spotify_client_secret
    SPOTIFY_REFRESH_TOKEN = var.spotify_refresh_token
  }
}

# Public HTTP invocation -- anyone can call the function's URL directly
# with no IAM auth header, computing a fresh response each time. Scoped
# to this function only, not a folder-wide grant.
resource "yandex_function_iam_binding" "public_invoke" {
  function_id = yandex_function.now_playing.id
  role        = "functions.functionInvoker"
  members     = ["system:allUsers"]
}
