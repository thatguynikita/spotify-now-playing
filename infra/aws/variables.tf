variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "function_name" {
  description = "Name for the Lambda function and related resources"
  type        = string
  default     = "spotify-now-playing"
}

variable "bucket_name" {
  description = "S3 bucket the function writes to. Must already exist if create_bucket is false; must be globally unique if Terraform is creating it."
  type        = string
}

variable "create_bucket" {
  description = "Whether Terraform creates the S3 bucket. Set to false to use a bucket you already manage -- Terraform will still attach a bucket policy granting public read on output_key, replacing any existing policy on that bucket (see README's Secrets section)."
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
