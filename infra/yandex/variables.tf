variable "folder_id" {
  description = "Yandex Cloud folder ID to deploy into"
  type        = string
}

variable "zone" {
  description = "Yandex Cloud availability zone"
  type        = string
  default     = "ru-central1-a"
}

variable "function_name" {
  description = "Name for the Cloud Function and related resources"
  type        = string
  default     = "spotify-now-playing"
}

variable "bucket_name" {
  description = "Object Storage bucket the function writes to. Must already exist if create_bucket is false; must be globally unique if Terraform is creating it."
  type        = string
}

variable "create_bucket" {
  description = "Whether Terraform creates the Object Storage bucket. Set to false to use a bucket you already manage -- write access still works via the storage service account's folder-level storage.editor role either way, but Terraform can only manage the bucket's public-read policy when it also owns the bucket resource (the Yandex provider ties policy to bucket creation, unlike AWS's separate policy resource) -- configure public read on an existing bucket yourself if you set this to false."
  type        = bool
  default     = true
}

variable "output_key" {
  description = "Object key (path) within the bucket to write to -- can be any path, not just the bucket root, e.g. \"assets/spotify/now-playing.json\""
  type        = string
  default     = "now-playing.json"
}

variable "spotify_client_id" {
  description = "Spotify app client ID"
  type        = string
  sensitive   = true
}

variable "spotify_client_secret" {
  description = "Spotify app client secret"
  type        = string
  sensitive   = true
}

variable "spotify_refresh_token" {
  description = "Spotify OAuth refresh token (see get_refresh_token.py to obtain one)"
  type        = string
  sensitive   = true
}
