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
  description = "Object Storage bucket to write to. Must exist already if create_bucket is false; must be globally unique otherwise."
  type        = string
}

variable "create_bucket" {
  description = "Whether Terraform creates the bucket. If false, use an existing bucket -- write access still works via the storage.editor role, but you must configure public read yourself (Yandex ties bucket policy to bucket creation)."
  type        = bool
  default     = true
}

variable "output_key" {
  description = "Object key (path) to write to within the bucket, e.g. \"assets/spotify/now-playing.json\"."
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
