$ErrorActionPreference = "Stop"
$payload = '{"text":"Hola cual es el horario","channel":"test","channel_user_id":"alex_pc"}'
$path = Join-Path $env:TEMP "axel.json"
Set-Content -Path $path -Value $payload -Encoding ascii
Write-Host "GET /health"
curl.exe -s http://127.0.0.1:8090/health
Write-Host ""
Write-Host "POST /webhooks/test"
curl.exe -s http://127.0.0.1:8090/webhooks/test -H "Content-Type: application/json" --data-binary "@$path"
Write-Host ""