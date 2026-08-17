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
