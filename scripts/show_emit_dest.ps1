$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
$doc = Get-Content -Raw (Join-Path $repo 'frontend\doc-139f3a8d.json') | ConvertFrom-Json
$doc.emitente | ConvertTo-Json -Depth 10
$doc.destinatario | ConvertTo-Json -Depth 10
