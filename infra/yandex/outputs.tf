output "now_playing_url" {
  description = "Public Object Storage URL serving the output object — point nginx's proxy_pass at this"
  value       = "https://storage.yandexcloud.net/${var.bucket_name}/${var.output_key}"
}

output "function_name" {
  value = yandex_function.now_playing.name
}
