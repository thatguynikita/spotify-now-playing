output "now_playing_url" {
  description = "Public S3 URL serving the output object — point nginx's proxy_pass at this"
  value       = "https://${var.bucket_name}.s3.${var.aws_region}.amazonaws.com/${var.output_key}"
}

output "lambda_function_name" {
  value = aws_lambda_function.now_playing.function_name
}
