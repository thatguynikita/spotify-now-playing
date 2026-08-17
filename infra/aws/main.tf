terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# boto3 ships with Lambda's Python runtime already, so the zip only
# needs the one shared script — no requirements.txt to bundle here.
data "archive_file" "lambda" {
  type        = "zip"
  output_path = "${path.module}/build/lambda.zip"

  source {
    content  = file("${path.module}/../../function/now_playing.py")
    filename = "now_playing.py"
  }
}

# S3 bucket ARNs are deterministic from just the name (no account ID
# or region component), so this works whether Terraform creates the
# bucket below or the caller brought their own existing one.
locals {
  bucket_arn = "arn:aws:s3:::${var.bucket_name}"
}

resource "aws_s3_bucket" "now_playing" {
  count  = var.create_bucket ? 1 : 0
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "now_playing" {
  count  = var.create_bucket ? 1 : 0
  bucket = aws_s3_bucket.now_playing[0].id

  # ACLs stay blocked (not used); the bucket policy below grants public
  # read on just the one object, so the *policy*-related blocks must be
  # off for that policy to take effect. Only managed when Terraform
  # owns the bucket -- an existing bucket's settings are left alone,
  # so if it already blocks public policies, the policy below will
  # fail to apply until you loosen that yourself.
  block_public_acls      = true
  ignore_public_acls     = true
  block_public_policy    = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "public_read_now_playing" {
  bucket = var.bucket_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadNowPlaying"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${local.bucket_arn}/${var.output_key}"
    }]
  })

  # References the whole (possibly zero-instance, if create_bucket is
  # false) resource rather than an index -- a no-op dependency edge
  # when there's nothing to wait on, instead of an invalid [0] index.
  depends_on = [aws_s3_bucket_public_access_block.now_playing]
}

resource "aws_iam_role" "lambda_exec" {
  name = "${var.function_name}-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3_write" {
  name = "${var.function_name}-s3-write"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "s3:PutObject"
      Resource = "${local.bucket_arn}/${var.output_key}"
    }]
  })
}

resource "aws_lambda_function" "now_playing" {
  function_name    = var.function_name
  role              = aws_iam_role.lambda_exec.arn
  handler           = "now_playing.aws_handler"
  runtime           = "python3.12"
  timeout           = 10
  filename          = data.archive_file.lambda.output_path
  source_code_hash  = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      OUTPUT_BUCKET          = var.bucket_name
      OUTPUT_KEY             = var.output_key
      SPOTIFY_CLIENT_ID      = var.spotify_client_id
      SPOTIFY_CLIENT_SECRET  = var.spotify_client_secret
      SPOTIFY_REFRESH_TOKEN  = var.spotify_refresh_token
    }
  }
}

resource "aws_iam_role" "scheduler_exec" {
  name = "${var.function_name}-scheduler-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "${var.function_name}-scheduler-invoke"
  role = aws_iam_role.scheduler_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.now_playing.arn
    }]
  })
}

# 1-minute floor is a hard limit of EventBridge Scheduler — no native
# sub-minute rate expressions. See README.md's Terraform section.
resource "aws_scheduler_schedule" "poll" {
  name                = "${var.function_name}-poll"
  schedule_expression = "rate(1 minute)"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.now_playing.arn
    role_arn = aws_iam_role.scheduler_exec.arn
  }
}
