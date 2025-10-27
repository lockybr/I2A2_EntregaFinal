$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
$jsonPath = Join-Path $repo 'backend\\api\\documents_db.json'
$outPath = Join-Path $repo 'frontend\\doc-139f3a8d.json'
$json = Get-Content -Raw -Path $jsonPath
$obj = ConvertFrom-Json $json
$doc = $obj.'139f3a8d-67ae-4764-bf78-7457948f6bf2'
$doc | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 $outPath
if (Test-Path $outPath) { Write-Output 'SAVED' } else { Write-Output 'FAILED' }
