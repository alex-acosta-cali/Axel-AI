$payload = '{"text":"Quiero un reembolso de mi compra","channel":"test","channel_user_id":"alex_pc"}'
$path = Join-Path $env:TEMP "axel_reemb.json"
Set-Content -Path $path -Value $payload -Encoding ascii
curl.exe -s http://127.0.0.1:8090/webhooks/test -H "Content-Type: application/json" --data-binary "@$path"
Write-Host ""