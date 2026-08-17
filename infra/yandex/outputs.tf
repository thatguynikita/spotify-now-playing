output "now_playing_url" {
  description = "Public HTTP URL that returns fresh now-playing JSON on every request — point your frontend's fetch() (or an nginx proxy_pass) at this"
  value       = "https://functions.yandexcloud.net/${yandex_function.now_playing.id}"
}

output "function_name" {
  value = yandex_function.now_playing.name
}
